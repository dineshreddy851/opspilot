import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";

await rm("dist", { force: true, recursive: true });
await mkdir("dist", { recursive: true });
await cp("static/index.html", "dist/index.html");
await cp("static/styles.css", "dist/styles.css");
await cp("static/config.js.example", "dist/config.js");
await writeFile("dist/app.js", await readFile("src/main.ts", "utf8"));

console.log("Built browser-ready files in web/dist.");
