// Tiny grayscale PNG writer for Data Matrix modules. No dependencies.
import { crc32, deflateSync } from "node:zlib";

export function modulesToPng(modules, width, height, options = {}) {
  const scale = options.scale || 8;
  const quiet = options.quiet ?? 2;
  const dark = options.dark ?? 1;
  const moduleWidth = width + quiet * 2;
  const moduleHeight = height + quiet * 2;
  const pixelWidth = moduleWidth * scale;
  const pixelHeight = moduleHeight * scale;
  const raw = Buffer.alloc((pixelWidth + 1) * pixelHeight);
  for (let y = 0; y < pixelHeight; y += 1) {
    const row = y * (pixelWidth + 1);
    raw[row] = 0;
    const moduleY = Math.floor(y / scale) - quiet;
    for (let x = 0; x < pixelWidth; x += 1) {
      const moduleX = Math.floor(x / scale) - quiet;
      let on = false;
      if (moduleX >= 0 && moduleY >= 0 && moduleX < width && moduleY < height) {
        on = modules[moduleY * width + moduleX] === dark;
      }
      raw[row + 1 + x] = on ? 0 : 255;
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(pixelWidth, 0);
  ihdr.writeUInt32BE(pixelHeight, 4);
  ihdr[8] = 8;
  ihdr[9] = 0;
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

function chunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body) >>> 0);
  return Buffer.concat([length, body, crc]);
}
