# Vendored animation libraries

These browser builds are checked into the repository so both pages work without a CDN or frontend build step.

- `gsap-3.15.0.min.js`: GSAP 3.15.0 browser distribution from the `gsap@3.15.0` npm package (`dist/gsap.min.js`). License: [GSAP Standard License](https://gsap.com/standard-license/). Browser global: `window.gsap`.
- `anime-4.5.0.umd.min.js`: Anime.js 4.5.0 UMD distribution from the `animejs@4.5.0` npm package (`dist/bundles/anime.umd.min.js`). License: MIT. Browser global: `window.AnimeJS`.

Load both regular scripts before a page's `type="module"` entry point. Update the versioned filenames and the matching HTML references together when upgrading.
