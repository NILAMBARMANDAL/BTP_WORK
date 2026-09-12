export function notFoundHandler(req, res) {
  res.status(404).json({ error: "Not found" });
}

// eslint-disable-next-line no-unused-vars
export function errorHandler(err, req, res, next) {
  // multer's own size-limit error doesn't set `.status` — map it to a 400
  // (client error: file too large) rather than letting it fall through to
  // a generic 500 (spec section 6: "return structured errors").
  const isMulterFileTooLarge = err.name === "MulterError" && err.code === "LIMIT_FILE_SIZE";
  const status = err.status ?? (isMulterFileTooLarge ? 400 : 500);
  const message = isMulterFileTooLarge ? "Audio file exceeds the maximum upload size" : err.message ?? "Internal server error";
  if (status >= 500) {
    console.error(err);
  }
  res.status(status).json({ error: message });
}
