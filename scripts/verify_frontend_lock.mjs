import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

const EXPECTED_SHA256 = 'cf1eb68b1988f16ec293040b0abf71e6007853d1cba089aa0f25a8d530c7c8df';
const lockPath = process.argv[2] ?? 'package-lock.json';
const contents = readFileSync(lockPath);
const actualSha256 = createHash('sha256').update(contents).digest('hex');

if (actualSha256 !== EXPECTED_SHA256) {
  console.error('Frontend dependency graph changed unexpectedly.');
  console.error(`Expected package-lock SHA-256: ${EXPECTED_SHA256}`);
  console.error(`Actual package-lock SHA-256:   ${actualSha256}`);
  process.exit(1);
}

console.log(`Verified frontend package-lock SHA-256: ${actualSha256}`);
