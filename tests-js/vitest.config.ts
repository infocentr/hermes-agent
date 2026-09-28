import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    include: ['**/*.test.ts', '**/*.test.mjs'],
    // Local carry (2026-09-28): upstream runs the JS checks on a 32-core runner;
    // this fork has no larger runners, so js-tests.yml is carried down to the
    // free 4-vCPU image. Several suites here shell out — bundle-smoke-metadata
    // and generate-icons spawn Node/Python children with spawnSync — and those
    // spawns starve under parallel vitest on 4 cores: `channel smoke binds the
    // complete admitted request` timed out at 15000ms in run 36389516801 while
    // its neighbour generate-icons legitimately took 20.6s. The work is not
    // hung, just slow, so give it real headroom. This was the ONLY thing
    // failing the required gate on that run. Drop if we ever get big runners.
    testTimeout: 60_000,
    hookTimeout: 60_000,
  },
})
