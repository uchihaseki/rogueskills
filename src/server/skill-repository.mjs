import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";

import { assertSkillGenome, validateSkillGenome } from "../skill-genome.js";

function now() {
  return new Date().toISOString();
}

function makeId(prefix, ...parts) {
  const base = parts.filter(Boolean).join("-").replace(/[^a-zA-Z0-9._-]+/g, "-");
  return `${prefix}-${base}-${Date.now().toString(36)}`;
}

function parseJson(value, fallback = null) {
  if (value == null) return fallback;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

export class SkillRepository {
  constructor(databasePath = "data/rogueskills.db") {
    if (databasePath !== ":memory:") mkdirSync(dirname(databasePath), { recursive: true });
    this.databasePath = databasePath;
    this.db = new DatabaseSync(databasePath);
    this.db.exec("PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL;");
    this.migrate();
  }

  migrate() {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS skills (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        lifecycle_status TEXT NOT NULL,
        current_version_id TEXT,
        source_id TEXT,
        source_url TEXT,
        license TEXT NOT NULL,
        risk_level TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );

      CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_source_fingerprint
        ON skills(fingerprint, source_url);
      CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(lifecycle_status);

      CREATE TABLE IF NOT EXISTS skill_versions (
        id TEXT PRIMARY KEY,
        skill_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        parent_version_id TEXT,
        genome_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(skill_id) REFERENCES skills(id) ON DELETE CASCADE,
        FOREIGN KEY(parent_version_id) REFERENCES skill_versions(id),
        UNIQUE(skill_id, version)
      );

      CREATE TABLE IF NOT EXISTS source_snapshots (
        id TEXT PRIMARY KEY,
        skill_id TEXT NOT NULL,
        source_url TEXT,
        revision TEXT,
        artifact_paths_json TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        content TEXT,
        fetched_at TEXT NOT NULL,
        FOREIGN KEY(skill_id) REFERENCES skills(id) ON DELETE CASCADE
      );

      CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_skill_fingerprint
        ON source_snapshots(skill_id, fingerprint);

      CREATE TABLE IF NOT EXISTS benchmark_runs (
        id TEXT PRIMARY KEY,
        skill_id TEXT NOT NULL,
        skill_version_id TEXT NOT NULL,
        benchmark_id TEXT NOT NULL,
        split TEXT NOT NULL,
        score REAL NOT NULL,
        passed INTEGER NOT NULL,
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(skill_id) REFERENCES skills(id) ON DELETE CASCADE,
        FOREIGN KEY(skill_version_id) REFERENCES skill_versions(id) ON DELETE CASCADE
      );

      CREATE INDEX IF NOT EXISTS idx_benchmark_skill ON benchmark_runs(skill_id, created_at DESC);
    `);
  }

  close() {
    this.db.close();
  }

  transaction(callback) {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const result = callback();
      this.db.exec("COMMIT");
      return result;
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }

  findSkillRow(id) {
    return this.db.prepare("SELECT * FROM skills WHERE id = ?").get(id) ?? null;
  }

  currentVersionRow(skillId) {
    return (
      this.db
        .prepare(
          `SELECT v.* FROM skill_versions v
           JOIN skills s ON s.current_version_id = v.id
           WHERE s.id = ?`,
        )
        .get(skillId) ?? null
    );
  }

  addVersion(skillId, genome, parentVersionId = null) {
    const latest = this.db
      .prepare("SELECT COALESCE(MAX(version), 0) AS version FROM skill_versions WHERE skill_id = ?")
      .get(skillId);
    const version = Number(latest.version) + 1;
    const versionId = `${skillId}@${version}`;
    this.db
      .prepare(
        `INSERT INTO skill_versions (id, skill_id, version, parent_version_id, genome_json, created_at)
         VALUES (?, ?, ?, ?, ?, ?)`,
      )
      .run(versionId, skillId, version, parentVersionId, JSON.stringify(genome), now());
    return { id: versionId, version };
  }

  upsertSkill(genome, { sourceId = "manual", snapshotContent = null } = {}) {
    assertSkillGenome(genome);
    const timestamp = now();
    const existing = this.findSkillRow(genome.id);

    return this.transaction(() => {
      let version;

      if (!existing) {
        this.db
          .prepare(
            `INSERT INTO skills (
              id, name, description, lifecycle_status, current_version_id,
              source_id, source_url, license, risk_level, fingerprint, created_at, updated_at
            ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)`,
          )
          .run(
            genome.id,
            genome.name,
            genome.description,
            genome.status,
            sourceId,
            genome.provenance.url,
            genome.metadata.license,
            genome.risk.level,
            genome.provenance.fingerprint,
            timestamp,
            timestamp,
          );
        version = this.addVersion(genome.id, genome);
      } else {
        const current = this.currentVersionRow(genome.id);
        const currentGenome = parseJson(current?.genome_json);
        if (currentGenome && JSON.stringify(currentGenome) === JSON.stringify(genome)) {
          version = { id: current.id, version: current.version };
        } else {
          version = this.addVersion(genome.id, genome, current?.id ?? null);
        }
        this.db
          .prepare(
            `UPDATE skills SET name = ?, description = ?, lifecycle_status = ?, source_id = ?,
              source_url = ?, license = ?, risk_level = ?, fingerprint = ?, updated_at = ?
             WHERE id = ?`,
          )
          .run(
            genome.name,
            genome.description,
            genome.status,
            sourceId,
            genome.provenance.url,
            genome.metadata.license,
            genome.risk.level,
            genome.provenance.fingerprint,
            timestamp,
            genome.id,
          );
      }

      this.db.prepare("UPDATE skills SET current_version_id = ? WHERE id = ?").run(version.id, genome.id);

      if (genome.provenance.fingerprint) {
        this.db
          .prepare(
            `INSERT OR IGNORE INTO source_snapshots (
              id, skill_id, source_url, revision, artifact_paths_json, fingerprint, content, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
          )
          .run(
            makeId("snapshot", genome.id, genome.provenance.fingerprint),
            genome.id,
            genome.provenance.url,
            genome.provenance.revision,
            JSON.stringify(genome.provenance.artifactPaths ?? []),
            genome.provenance.fingerprint,
            snapshotContent,
            genome.provenance.capturedAt || timestamp,
          );
      }

      return this.getSkill(genome.id);
    });
  }

  recordEvaluation(skillId, benchmarkId, split, result) {
    const skill = this.findSkillRow(skillId);
    if (!skill) throw new Error(`Skill not found: ${skillId}`);
    const version = this.currentVersionRow(skillId);
    const id = result.runId || makeId("benchmark", skillId, benchmarkId);
    this.db
      .prepare(
        `INSERT INTO benchmark_runs (
          id, skill_id, skill_version_id, benchmark_id, split, score, passed, result_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        id,
        skillId,
        version.id,
        benchmarkId,
        split,
        result.score,
        result.passed ? 1 : 0,
        JSON.stringify(result),
        now(),
      );
    return this.getEvaluation(id);
  }

  getEvaluation(id) {
    const row = this.db.prepare("SELECT * FROM benchmark_runs WHERE id = ?").get(id);
    if (!row) return null;
    return {
      id: row.id,
      skillId: row.skill_id,
      skillVersionId: row.skill_version_id,
      benchmarkId: row.benchmark_id,
      split: row.split,
      score: row.score,
      passed: Boolean(row.passed),
      result: parseJson(row.result_json, {}),
      createdAt: row.created_at,
    };
  }

  listEvaluations(skillId) {
    return this.db
      .prepare("SELECT id FROM benchmark_runs WHERE skill_id = ? ORDER BY created_at DESC")
      .all(skillId)
      .map((row) => this.getEvaluation(row.id));
  }

  promoteToInitial(skillId, evaluationId) {
    const skill = this.getSkill(skillId);
    if (!skill) throw new Error(`Skill not found: ${skillId}`);
    const evaluation = this.getEvaluation(evaluationId);
    if (!evaluation || evaluation.skillId !== skillId || !evaluation.passed) {
      throw new Error("通过的准入评估是进入 Initial Skill Library 的必要条件");
    }
    if (evaluation.benchmarkId !== "library-admission-v1") {
      throw new Error("评估不是 Initial Library 准入套件");
    }

    const validation = validateSkillGenome(skill.genome);
    if (!validation.valid) throw new Error("Skill Genome 未通过 Schema 验证");
    if (["unknown", "NOASSERTION"].includes(skill.genome.metadata.license)) throw new Error("许可证未知");
    if (skill.genome.risk.level === "high") throw new Error("高风险 Skill 不能进入 Initial Library");

    const promoted = {
      ...skill.genome,
      status: "initial",
      evaluation: {
        ...skill.genome.evaluation,
        status: "passed",
        lastRunId: evaluation.id,
        score: evaluation.score,
      },
    };
    return this.upsertSkill(promoted, { sourceId: skill.sourceId });
  }

  listSkills({ status = null } = {}) {
    const rows = status
      ? this.db.prepare("SELECT id FROM skills WHERE lifecycle_status = ? ORDER BY updated_at DESC").all(status)
      : this.db.prepare("SELECT id FROM skills ORDER BY updated_at DESC").all();
    return rows.map((row) => this.getSkill(row.id));
  }

  listInitialSkills() {
    return this.listSkills({ status: "initial" });
  }

  deleteSkill(id) {
    const skill = this.findSkillRow(id);
    if (!skill) return false;
    if (skill.lifecycle_status !== "quarantine") {
      throw new Error("只有 Quarantine Skill 可以直接移除");
    }
    this.db.prepare("DELETE FROM skills WHERE id = ?").run(id);
    return true;
  }

  getSkill(id) {
    const row = this.findSkillRow(id);
    if (!row) return null;
    const current = this.currentVersionRow(id);
    const versions = this.db
      .prepare("SELECT id, version, parent_version_id, created_at FROM skill_versions WHERE skill_id = ? ORDER BY version DESC")
      .all(id)
      .map((version) => ({
        id: version.id,
        version: version.version,
        parentVersionId: version.parent_version_id,
        createdAt: version.created_at,
      }));
    const snapshots = this.db
      .prepare(
        "SELECT id, source_url, revision, artifact_paths_json, fingerprint, fetched_at FROM source_snapshots WHERE skill_id = ? ORDER BY fetched_at DESC",
      )
      .all(id)
      .map((snapshot) => ({
        id: snapshot.id,
        sourceUrl: snapshot.source_url,
        revision: snapshot.revision,
        artifactPaths: parseJson(snapshot.artifact_paths_json, []),
        fingerprint: snapshot.fingerprint,
        fetchedAt: snapshot.fetched_at,
      }));

    return {
      id: row.id,
      name: row.name,
      description: row.description,
      status: row.lifecycle_status,
      currentVersionId: row.current_version_id,
      sourceId: row.source_id,
      sourceUrl: row.source_url,
      license: row.license,
      riskLevel: row.risk_level,
      fingerprint: row.fingerprint,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
      genome: parseJson(current?.genome_json, null),
      versions,
      snapshots,
      evaluations: this.listEvaluations(id),
    };
  }
}
