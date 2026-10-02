import type { TestProjectConfiguration } from 'vitest/config'
import { defineConfig } from 'vitest/config'

const reactUi: TestProjectConfiguration = {
  extends: './vite.config.ts',
  test: {
    name: 'ui',
    environment: 'jsdom',
    // Keep padding regressions observable instead of mocking the stylesheet away.
    css: { include: [/status-stack\.css$/] },
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    globals: true,
    // React 19.1+ stubs `react`.act to undefined in the production build;
    // @testing-library/react's act() delegates to it and throws
    // "React.act is not a function" when NODE_ENV=production. Force the
    // development build for the test worker so `act` resolves to a real
    // function, regardless of any ambient NODE_ENV (e.g. a shell that
    // inherited NODE_ENV=production from a desktop launch).
    env: { NODE_ENV: 'development' },
    // The first test in each file pays jsdom env init + full module transform,
    // which can exceed vitest's 5000ms default under CI/load. 15s gives the
    // cold start headroom without masking genuinely hung tests. Hooks pay the
    // same cold cost when a beforeEach does `vi.resetModules()` + `await
    // import(...)` (65 files); one timed out at 10s on CI (#120318).
    // Local carry (2026-09-28): the numbers above were tuned for upstream's
    // 32-core runner. Our runner-downgrade carry puts js-tests.yml on the free
    // 4-vCPU image, where the same cold-start cost lands on ~8x less CPU, so
    // raise the headroom in the same spirit and for the same reason.
    testTimeout: 45_000,
    hookTimeout: 60_000,
    // `retry` is for a different failure than the timeouts: on 4 cores this
    // suite loses render/effect races and fails an ASSERTION rather than timing
    // out — run 36389516801 hit `desktop-install-overlay > dismisses a failed
    // install on Escape`: "expected <h2/> to be null", i.e. it asserted before
    // the dismiss landed. It is a known ROTATING flake (a different test each
    // run) in code we carry ZERO delta in, so retrying is honest: a real break
    // fails all three attempts, a scheduling race passes on the second. Prefer
    // this to masking the whole js-tests lane, which would throw away the only
    // JS signal we have. Drop with the runner downgrade.
    retry: 2
  }
}

const electronNative: TestProjectConfiguration = {
  test: {
    name: 'electron',
    environment: 'node',
    // `e2e/**/*.unit.test.ts` is the e2e HELPERS, not the specs: plain node
    // modules that should be provable without booting Electron. Playwright
    // ignores the same pattern so they run in exactly one runner.
    include: ['electron/**/*.test.ts', 'scripts/**.test.{ts,mjs}', 'e2e/**/*.unit.test.ts']
  }
}

export default defineConfig({
  test: {
    globalSetup: ['./vitest.run-tmp.ts'],
    projects: [reactUi, electronNative]
  }
})
