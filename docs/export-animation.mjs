// Export docs/data-flow-live.html (or any page exposing window.render(t) + ?export=1) to PNG frames, then MP4 (+ GIF with --gif).
// usage: node docs/export-animation.mjs <page.html> <out-dir> [--theme dark|light] [--fps 30] [--width 1000] [--gif] [--still 15]
//   --still <t>  only write one PNG at time t (for checking a frame)
// needs: playwright in the current directory (npm i -D playwright; uses installed Chrome), ffmpeg; gifski for --gif.
// If Chrome isn't installed, set PW_EXECUTABLE to a Chromium binary (e.g. one under ~/Library/Caches/ms-playwright).
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

let chromium;
try { ({ chromium } = createRequire(process.cwd() + '/')('playwright')); }
catch { console.error('playwright not found in ' + process.cwd() + ' — run: npm i -D playwright'); process.exit(1); }

const [page, out, ...rest] = process.argv.slice(2);
if (!page || !out) { console.error('usage: node docs/export-animation.mjs <page.html> <out-dir> [--theme dark|light] [--fps 30] [--width 1000] [--gif] [--still t]'); process.exit(1); }
const opt = (k, d) => { const i = rest.indexOf('--' + k); return i >= 0 ? rest[i + 1] : d; };
const theme = opt('theme', 'dark'), fps = +opt('fps', 30), width = +opt('width', 1000), still = opt('still', null);
const name = path.basename(page, '.html') + '-' + theme;
fs.mkdirSync(out, { recursive: true });

const launch = process.env.PW_EXECUTABLE ? { executablePath: process.env.PW_EXECUTABLE } : { channel: 'chrome' };
const b = await chromium.launch(launch);
const p = await b.newPage({ viewport: { width: width + 40, height: 1200 }, deviceScaleFactor: 2 });
const errors = []; p.on('pageerror', (e) => errors.push(e.message));
await p.goto('file://' + path.resolve(page) + '?export=1&theme=' + theme);
await p.evaluate(() => document.fonts.ready);
const win = p.locator('#win');

if (still !== null) {
  await p.evaluate((t) => window.render(t), +still);
  const f = path.join(out, `${name}-t${still}.png`);
  await win.screenshot({ path: f });
  console.log('wrote', f, errors.length ? 'page errors: ' + errors.join('; ') : '(no page errors)');
  await b.close(); process.exit(0);
}

const loop = await p.evaluate(() => window.LOOP);
const frames = path.join(out, name + '-frames');
fs.rmSync(frames, { recursive: true, force: true }); fs.mkdirSync(frames);
for (let i = 0; i < loop * fps; i++) {
  await p.evaluate((t) => window.render(t), i / fps);
  await win.screenshot({ path: path.join(frames, String(i).padStart(4, '0') + '.png') });
}
await b.close();
if (errors.length) console.warn('page errors:', errors);

const even = `scale=${width}:-2:flags=lanczos`;
execFileSync('ffmpeg', ['-v', 'error', '-y', '-framerate', String(fps), '-i', path.join(frames, '%04d.png'),
  '-vf', `${even},format=yuv420p`, '-c:v', 'libx264', '-crf', '20', '-movflags', '+faststart', path.join(out, name + '.mp4')]);
if (rest.includes('--gif')) {
  const pngs = fs.readdirSync(frames).sort().filter((_, i) => i % Math.max(1, Math.round(fps / 15)) === 0).map((f) => path.join(frames, f));
  execFileSync('gifski', ['-q', '--fps', String(Math.min(fps, 15)), '--width', String(width), '--quality', '85', '-o', path.join(out, name + '.gif'), ...pngs]);
}
fs.rmSync(frames, { recursive: true, force: true });
console.log('wrote', path.join(out, name + '.mp4') + (rest.includes('--gif') ? ' and .gif' : ''));
