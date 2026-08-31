// Copies the React dashboard's static export (dashboard/out) into public/,
// replacing the old hand-written public/index.html dashboard entirely.
// Plain Node fs (no shell cp/xcopy) so this runs identically on Windows/Unix/CI.
import { cpSync, existsSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(root, '..', 'dashboard', 'out');
const dest = path.join(root, '..', 'public');

if (!existsSync(src)) {
  console.error(`[copy-dashboard-build] ${src} does not exist — run "npm run build" in dashboard/ first.`);
  process.exit(1);
}

rmSync(dest, { recursive: true, force: true });
cpSync(src, dest, { recursive: true });
console.log(`[copy-dashboard-build] copied ${src} -> ${dest}`);
