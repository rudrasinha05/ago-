import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir: '.', testMatch: '*.spec.mjs', timeout:45000,
  // WebKit browser processes occasionally crashed when competing for memory
  // with other browser projects on GitHub's shared runner. Keep all projects,
  // assertions, and zero retries; serialize only the CI browser executions.
  workers: process.env.CI ? 1 : 2, retries: 0,
  use:{baseURL:'http://127.0.0.1:18776',reducedMotion:'reduce',trace:'retain-on-failure'},
  // In CI the github reporter also writes each failure as a check annotation,
  // so the failing test and error are visible without downloading artifacts.
  reporter:[['list'],...(process.env.CI?[['github']]:[]),['html',{outputFolder:'artifacts/report',open:'never'}]],
  outputDir:'artifacts/results',
  webServer:{command:'AGO_ENVIRONMENT=development python -m uvicorn ago.main:app --host 127.0.0.1 --port 18776 --no-proxy-headers',url:'http://127.0.0.1:18776/health/live',reuseExistingServer:!process.env.CI,timeout:30000},
  projects:[
    {name:'chromium-desktop',use:{browserName:'chromium',viewport:{width:1440,height:900}}},
    {name:'firefox-desktop',use:{browserName:'firefox',viewport:{width:1440,height:900}}},
    {name:'webkit-desktop',use:{browserName:'webkit',viewport:{width:1440,height:900}}},
    {name:'chromium-phone',use:{browserName:'chromium',viewport:{width:390,height:844},isMobile:true,hasTouch:true}},
    {name:'firefox-tablet',use:{browserName:'firefox',viewport:{width:820,height:1180}}},
    {name:'webkit-phone',use:{browserName:'webkit',viewport:{width:390,height:844},isMobile:true,hasTouch:true}},
  ],
});
