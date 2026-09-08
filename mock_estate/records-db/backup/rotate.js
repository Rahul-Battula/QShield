// Nightly backup encryption for the records database dumps.
// Rewritten in 2023 — this one is actually fine, and is here as a control:
// the scanner should classify it QUANTUM_SAFE, not flag it.

const crypto = require("crypto");

function encryptDump(plaintext, key) {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", key, iv);
  const enc = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  return { iv, tag: cipher.getAuthTag(), data: enc };
}

function dumpChecksum(buf) {
  return crypto.createHash("sha512").update(buf).digest("hex");
}

module.exports = { encryptDump, dumpChecksum };
