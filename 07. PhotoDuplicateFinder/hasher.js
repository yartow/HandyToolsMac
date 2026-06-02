const Jimp = require('jimp')
const path = require('path')

const HEIC_EXTS = new Set(['heic', 'heif'])
const HASH_SIZE = 8   // produces a 63-bit hash (8×8 minus DC term)

function isHeic(filePath) {
  const ext = path.extname(filePath).slice(1).toLowerCase()
  return HEIC_EXTS.has(ext)
}

// ---------------------------------------------------------------------------
// 1-D Discrete Cosine Transform (Type-II)
// ---------------------------------------------------------------------------
function dct1d(signal) {
  const N = signal.length
  const result = new Array(N)
  for (let k = 0; k < N; k++) {
    let sum = 0
    for (let n = 0; n < N; n++) {
      sum += signal[n] * Math.cos((Math.PI / N) * (n + 0.5) * k)
    }
    result[k] = sum
  }
  return result
}

// 2-D DCT: apply 1-D DCT to each row, then each column
function dct2d(matrix) {
  const N = matrix.length
  const rowDct = matrix.map(row => dct1d(row))
  // Transpose
  const transposed = Array.from({ length: N }, (_, i) => rowDct.map(row => row[i]))
  const colDct = transposed.map(row => dct1d(row))
  // Transpose back
  return Array.from({ length: N }, (_, i) => colDct.map(row => row[i]))
}

// ---------------------------------------------------------------------------
// Compute 63-bit perceptual hash (pHash) as BigInt
// ---------------------------------------------------------------------------
async function computeHash(imagePath) {
  if (isHeic(imagePath)) {
    throw Object.assign(new Error('HEIC not supported'), { unsupported: true })
  }

  const image = await Jimp.read(imagePath)
  image.resize(32, 32).greyscale()

  // Build 32×32 pixel matrix (0–255, R channel since greyscale R=G=B)
  const pixels = []
  for (let y = 0; y < 32; y++) {
    const row = []
    for (let x = 0; x < 32; x++) {
      const idx = (y * 32 + x) * 4
      row.push(image.bitmap.data[idx])
    }
    pixels.push(row)
  }

  const dct = dct2d(pixels)

  // Extract top-left 8×8 low-frequency coefficients, skip [0][0] DC term
  const lowFreq = []
  for (let y = 0; y < HASH_SIZE; y++) {
    for (let x = 0; x < HASH_SIZE; x++) {
      if (y === 0 && x === 0) continue
      lowFreq.push(dct[y][x])
    }
  }

  const mean = lowFreq.reduce((s, v) => s + v, 0) / lowFreq.length

  let hash = 0n
  for (let i = 0; i < lowFreq.length; i++) {
    if (lowFreq[i] >= mean) hash |= (1n << BigInt(i))
  }
  return hash
}

// ---------------------------------------------------------------------------
// Hamming distance between two BigInt hashes
// ---------------------------------------------------------------------------
function hammingDistance(hashA, hashB) {
  let x = hashA ^ hashB
  let count = 0
  while (x > 0n) {
    count += Number(x & 1n)
    x >>= 1n
  }
  return count
}

module.exports = { computeHash, hammingDistance, isHeic }
