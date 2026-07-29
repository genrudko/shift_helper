import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

const EXPECTED_SEMANTIC_SHA256 = '4b7b9079cef680b287fafda404df2fa151246706de1a6fff769feead57d7ecc4';
const lockPath = process.argv[2] ?? 'package-lock.json';

function canonicalize(value) {
  if (Array.isArray(value)) {
    return value.map(canonicalize);
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonicalize(value[key])])
    );
  }
  return value;
}

const parsedLock = JSON.parse(readFileSync(lockPath, 'utf8'));
const canonicalLock = JSON.stringify(canonicalize(parsedLock));
const actualSemanticSha256 = createHash('sha256').update(canonicalLock).digest('hex');

if (actualSemanticSha256 !== EXPECTED_SEMANTIC_SHA256) {
  console.error('Frontend dependency graph changed unexpectedly.');
  console.error(`Expected semantic SHA-256: ${EXPECTED_SEMANTIC_SHA256}`);
  console.error(`Actual semantic SHA-256:   ${actualSemanticSha256}`);
  process.exit(1);
}

console.log(`Verified frontend dependency graph: ${actualSemanticSha256}`);
