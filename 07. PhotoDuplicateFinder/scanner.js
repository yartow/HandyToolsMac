const IMAGE_EXTENSIONS = new Set([
  'jpg', 'jpeg', 'png', 'heic', 'heif', 'webp', 'tiff', 'tif', 'raw', 'dng', 'cr2', 'arw',
])

function isImageFile(name) {
  const dot = name.lastIndexOf('.')
  if (dot < 0) return false
  return IMAGE_EXTENSIONS.has(name.slice(dot + 1).toLowerCase())
}

function normalise(filename) {
  const dot = filename.lastIndexOf('.')
  const base = dot >= 0 ? filename.slice(0, dot) : filename
  return base.toLowerCase().trim()
}

function filterPhotos(lsjsonItems, remote) {
  return lsjsonItems
    .filter(item => !item.IsDir && isImageFile(item.Name))
    .map(item => ({
      remote,
      path: item.Path,
      name: item.Name,
      size: item.Size,
      normName: normalise(item.Name),
      isKeep: false,
      canDelete: false,
      thumbPath: null,
      hashVerified: null,
    }))
}

function buildDuplicateGroups(driveFiles, photosFiles, driveRemote) {
  const map = new Map()

  for (const f of [...driveFiles, ...photosFiles]) {
    const arr = map.get(f.normName) ?? []
    arr.push(f)
    map.set(f.normName, arr)
  }

  const groups = []

  for (const [normName, files] of map) {
    const hasDrive  = files.some(f => f.remote === driveRemote)
    const hasPhotos = files.some(f => f.remote !== driveRemote)
    const isDriveDup = hasDrive && !hasPhotos && files.length >= 2

    if (!((hasDrive && hasPhotos) || isDriveDup)) continue

    const sorted = [...files].sort((a, b) => b.size - a.size)
    sorted[0].isKeep = true
    sorted.slice(1).forEach(f => { f.isKeep = false })
    sorted.forEach(f => { f.canDelete = f.remote === driveRemote && !f.isKeep })

    groups.push({ id: normName, normName, files: sorted })
  }

  groups.sort((a, b) => {
    const recA = a.files.filter(f => f.canDelete).reduce((s, f) => s + f.size, 0)
    const recB = b.files.filter(f => f.canDelete).reduce((s, f) => s + f.size, 0)
    return recB - recA
  })

  return groups
}

module.exports = { filterPhotos, buildDuplicateGroups, normalise, isImageFile, IMAGE_EXTENSIONS }
