import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    include: ['**/*.test.ts', '**/*.test.mjs'],
    // Local carry (2026-09-28): upstream runs the JS checks on a 32-core runner;
    // this fork has no larger runners, so js-tests.yml is carried down to the
    // free 4-vCPU image, where the spawn-heavy suites here starve under
    // parallel vitest (generate-icons legitimately takes ~20.6s). This raises
    // the FLOOR for the ~29 files that declare no timeout of their own.
    // NOTE: it does NOT help a test that passes its own timeout as vitest's
    // third argument — that always wins. The `channel smoke` failure was
    // exactly that case and had to be fixed at the call site in
    // bundle-smoke-metadata.test.mjs; raising it here did nothing (proven by
    // run 36397500339, which still reported "timed out in 15000ms").
    // Drop with the runner downgrade if we ever get big runners.
    testTimeout: 60_000,
    hookTimeout: 60_000,
  },
})
