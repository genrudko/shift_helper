import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

const EXPECTED_SEMANTIC_SHA256 = '0bc9075c92c2da7d16d8d8eb09602a28c9c74c9404bc2526de8c47e752b3860c';
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
