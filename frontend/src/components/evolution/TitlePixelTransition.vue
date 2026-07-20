<script setup lang="ts">
import { nextTick, onBeforeUnmount, shallowRef, watch } from 'vue'

type Tile = {
  canvas: HTMLCanvasElement
  x: number
  y: number
  width: number
  height: number
  delay: number
  drift: number
  rotation: number
}

const props = defineProps<{
  source: HTMLCanvasElement
  direction: 'fall' | 'cover'
  active: boolean
}>()
const emit = defineEmits<{ ready: []; done: [] }>()
const tiles = shallowRef<Tile[]>([])
const tileElements: HTMLCanvasElement[] = []
let finishTimer: number | undefined
let cleaned = false

function setTileElement(element: unknown, index: number) {
  const canvas = element as HTMLCanvasElement | null
  if (canvas?.tagName === 'CANVAS') tileElements[index] = canvas
}

async function buildTiles() {
  const columns = window.innerWidth < 760 ? 8 : 12
  const rows = window.innerWidth < 760 ? 12 : 8
  const source = props.source
  const tileWidth = source.width / columns
  const tileHeight = source.height / rows
  const next: Tile[] = []

  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      const index = row * columns + column
      const canvas = document.createElement('canvas')
      const width = Math.ceil(tileWidth)
      const height = Math.ceil(tileHeight)
      canvas.width = width
      canvas.height = height
      canvas.getContext('2d')?.drawImage(
        source,
        column * tileWidth,
        row * tileHeight,
        tileWidth,
        tileHeight,
        0,
        0,
        width,
        height,
      )
      next.push({
        canvas,
        x: column * (100 / columns),
        y: row * (100 / rows),
        width: 100 / columns,
        height: 100 / rows,
        delay: ((index * 73 + 19) % 97) * 4,
        drift: ((index * 47 + 11) % 15) - 7,
        rotation: ((index * 31 + 7) % 9) - 4,
      })
    }
  }

  tiles.value = next
  await nextTick()
  next.forEach((tile, index) => {
    const target = tileElements[index]
    const context = target?.getContext('2d')
    if (!target || !context) return
    context.clearRect(0, 0, target.width, target.height)
    context.drawImage(tile.canvas, 0, 0)
  })
  await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
  emit('ready')
}

function cleanup() {
  if (cleaned) return
  cleaned = true
  if (finishTimer) window.clearTimeout(finishTimer)
  tileElements.length = 0
  tiles.value.forEach((tile) => {
    tile.canvas.width = 0
    tile.canvas.height = 0
  })
  tiles.value = []
}

watch(() => props.active, (active) => {
  if (!active) return
  finishTimer = window.setTimeout(() => emit('done'), 1450)
})

buildTiles()
onBeforeUnmount(cleanup)
</script>

<template>
  <div
    class="real-tile-overlay"
    :class="[`real-tile-${direction}`, { 'is-active': active }]"
    aria-hidden="true"
  >
    <canvas
      v-for="(tile, index) in tiles"
      :key="`${tile.x}-${tile.y}`"
      class="real-tile"
      :width="tile.canvas.width"
      :height="tile.canvas.height"
      :style="{
        left: `${tile.x}%`,
        top: `${tile.y}%`,
        width: `${tile.width}%`,
        height: `${tile.height}%`,
        '--tile-delay': `${tile.delay}ms`,
        '--tile-drift': `${tile.drift}vw`,
        '--tile-rotation': `${tile.rotation}deg`,
      }"
      :ref="(element) => setTileElement(element, index)"
    />
  </div>
</template>
