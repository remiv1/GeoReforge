import { cp, mkdir } from 'node:fs/promises';

const target = 'src/api/web/static/vendor';
await mkdir(target, { recursive: true });
await Promise.all([
    ['node_modules/htmx.org/dist/htmx.min.js', 'htmx.min.js'],
    ['node_modules/gsap/dist/gsap.min.js', 'gsap.min.js'],
    ['node_modules/leaflet/dist', 'leaflet'],
    ['node_modules/lucide/dist/umd/lucide.min.js', 'lucide.min.js'],
    ['doc/img/logo.png', 'logo.png'],
].map(([source, destination]) => cp(source, `${target}/${destination}`, { recursive: true })));
await mkdir(`${target}/fonts`, { recursive: true });
await Promise.all([400, 500, 600].map((weight) => {
    const file = `ibm-plex-sans-latin-${weight}-normal.woff2`;
    return cp(`node_modules/@fontsource/ibm-plex-sans/files/${file}`, `${target}/fonts/${file}`);
}));
