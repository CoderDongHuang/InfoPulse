/** Treat dismissing a dialog as a normal exit; preserve unexpected failures. */
export async function runDialog<T>(open: () => Promise<T>): Promise<T | undefined> {
  try {
    return await open()
  } catch (action) {
    if (action === 'cancel' || action === 'close') return undefined
    throw action
  }
}
