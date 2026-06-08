'use strict'

// ---------------------------------------------------------------------------
// String utilities
// ---------------------------------------------------------------------------

function levenshtein(a, b) {
  const m = a.length, n = b.length
  if (m === 0) return n
  if (n === 0) return m
  const prev = Array.from({ length: n + 1 }, (_, j) => j)
  const curr = new Array(n + 1)
  for (let i = 1; i <= m; i++) {
    curr[0] = i
    for (let j = 1; j <= n; j++) {
      curr[j] = a[i-1] === b[j-1]
        ? prev[j-1]
        : 1 + Math.min(prev[j], curr[j-1], prev[j-1])
    }
    for (let j = 0; j <= n; j++) prev[j] = curr[j]
  }
  return prev[n]
}

function stringSim(a, b) {
  if (!a && !b) return 1
  if (!a || !b) return 0
  const dist = levenshtein(a, b)
  return 1 - dist / Math.max(a.length, b.length)
}

// Strip copy indicators: "(1)", " - Copy", "_copy 2", etc.  Don't touch numeric
// filename stems like "IMG_1234" — those aren't duplicate suffixes.
function stripDupSuffix(s) {
  return s
    .replace(/\s*-\s*copy(\s+\d+)?$/i, '')   // " - Copy 2"
    .replace(/[_ ]\s*copy(\s+\d+)?$/i,  '')   // "_copy", " copy 2"
    .replace(/\s*\(\d{1,4}\)$/,          '')   // "(1)", " (12)"
    .trim()
}

// ---------------------------------------------------------------------------
// Signal: filename (max 20 pts)
// ---------------------------------------------------------------------------

function scoreFilename(normA, normB) {
  if (!normA && !normB) return 20
  if (!normA || !normB) return 0
  if (normA === normB) return 20

  const sa = stripDupSuffix(normA)
  const sb = stripDupSuffix(normB)
  if (sa && sb && sa === sb) return 15
  if (sa && sb && (sa.startsWith(sb) || sb.startsWith(sa))) return 12

  const sim = stringSim(normA, normB)
  if (sim >= 0.85) return 10
  if (sim >= 0.70) return 6
  if (sim >= 0.50) return 3
  return 0
}

// ---------------------------------------------------------------------------
// Signal: file size (max 20 pts)
// ---------------------------------------------------------------------------

function scoreSize(sizeA, sizeB) {
  if (!sizeA || !sizeB) return 0
  if (sizeA === sizeB) return 20
  const diff = Math.abs(sizeA - sizeB) / Math.max(sizeA, sizeB)
  if (diff < 0.01) return 18
  if (diff < 0.05) return 15
  if (diff < 0.10) return 8
  if (diff < 0.20) return 3
  return 0
}

// ---------------------------------------------------------------------------
// Signal: EXIF (max 50 pts: resolution 15, camera 15, lens 10, date 10)
// ---------------------------------------------------------------------------

function parseExifDate(val) {
  if (!val) return null
  if (val instanceof Date) return isNaN(val.getTime()) ? null : val
  if (typeof val === 'string') {
    const fixed = val.replace(/^(\d{4}):(\d{2}):(\d{2})/, '$1-$2-$3')
    const d = new Date(fixed)
    return isNaN(d.getTime()) ? null : d
  }
  return null
}

function scoreExif(exifA, exifB) {
  const out = { resolution: 0, camera: 0, lens: 0, date: 0 }
  if (!exifA || !exifB) return out

  // Resolution
  const wA = exifA.ImageWidth  || exifA.ExifImageWidth
  const hA = exifA.ImageHeight || exifA.ExifImageHeight
  const wB = exifB.ImageWidth  || exifB.ExifImageWidth
  const hB = exifB.ImageHeight || exifB.ExifImageHeight
  if (wA && hA && wB && hB && wA === wB && hA === hB) out.resolution = 15

  // Camera make + model
  const camA = [exifA.Make, exifA.Model].filter(Boolean).join(' ').toLowerCase().trim()
  const camB = [exifB.Make, exifB.Model].filter(Boolean).join(' ').toLowerCase().trim()
  if (camA && camB) {
    if (camA === camB) out.camera = 15
    else if (exifA.Make && exifB.Make &&
             exifA.Make.toLowerCase() === exifB.Make.toLowerCase()) out.camera = 7
  }

  // Lens model
  const lensA = (exifA.LensModel || exifA.Lens || '').toLowerCase().trim()
  const lensB = (exifB.LensModel || exifB.Lens || '').toLowerCase().trim()
  if (lensA && lensB && lensA === lensB) out.lens = 10

  // Date taken
  const da = parseExifDate(exifA.DateTimeOriginal || exifA.CreateDate || exifA.DateTime)
  const db = parseExifDate(exifB.DateTimeOriginal || exifB.CreateDate || exifB.DateTime)
  if (da && db) {
    const diffSec = Math.abs(da.getTime() - db.getTime()) / 1000
    if (diffSec <= 60)   out.date = 10
    else if (diffSec <= 300) out.date = 5
  }

  return out
}

// ---------------------------------------------------------------------------
// Combined score (0–100)
// ---------------------------------------------------------------------------

function computeScore({ normNameA, normNameB, sizeA, sizeB, exifA, exifB, pHashDistance, heic }) {
  const fn  = scoreFilename(normNameA, normNameB)
  const sz  = scoreSize(sizeA, sizeB)
  const ex  = scoreExif(exifA, exifB)
  const exifAvailable = !!(exifA || exifB)

  const phNa = !!(heic || pHashDistance === null || pHashDistance === undefined)
  const ph   = phNa ? 0 : pHashDistance <= 10 ? 20 : pHashDistance <= 20 ? 10 : 0

  const raw   = fn + sz + ex.resolution + ex.camera + ex.lens + ex.date + ph
  const score = Math.min(100, raw)

  return {
    score,
    breakdown: [
      { signal: 'Filename',    score: fn,            max: 20, na: false },
      { signal: 'File size',   score: sz,            max: 20, na: false },
      { signal: 'Resolution',  score: ex.resolution, max: 15, na: !exifAvailable },
      { signal: 'Camera',      score: ex.camera,     max: 15, na: !exifAvailable },
      { signal: 'Lens',        score: ex.lens,       max: 10, na: !exifAvailable },
      { signal: 'Date taken',  score: ex.date,       max: 10, na: !exifAvailable },
      { signal: 'Visual hash', score: ph,            max: 20, na: phNa },
    ],
  }
}

module.exports = { computeScore }
