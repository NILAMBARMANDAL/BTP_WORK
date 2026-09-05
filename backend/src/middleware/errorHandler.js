export function notFoundHandler(req, res) {
  res.status(404).json({ error: "Not found" });
}

// eslint-disable-next-line no-unused-vars
export function errorHandler(err, req, res, next) {
  const status = err.status ?? (err.name === "MlServiceError" ? err.status : 500);
  const message = err.message ?? "Internal server error";
  if (status >= 500) {
    console.error(err);
  }
  res.status(status).json({ error: message });
}
