const MAX_EDGE = 1600;
const QUALITIES = [0.85, 0.7, 0.55, 0.4];

function toBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("The photo could not be processed."))),
      "image/jpeg",
      quality,
    );
  });
}

/** Downscales and re-encodes a photo as JPEG so uploads are small and always within the limit. */
export async function prepareImage(file: File, maxBytes: number): Promise<Blob> {
  if (!file.type.startsWith("image/")) throw new Error("Choose an image file.");

  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file); // honours EXIF orientation
  } catch {
    throw new Error("That image format isn't supported. Try a JPEG or PNG photo.");
  }

  const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(bitmap.width * scale));
  canvas.height = Math.max(1, Math.round(bitmap.height * scale));
  const context = canvas.getContext("2d");
  if (!context) throw new Error("The photo could not be processed.");
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();

  for (const quality of QUALITIES) {
    const blob = await toBlob(canvas, quality);
    if (blob.size <= maxBytes) return blob;
  }
  throw new Error("That photo is too large. Try a smaller one.");
}
