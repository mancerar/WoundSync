import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.woundsync.app',
  appName: 'WoundSync',
  webDir: 'out',
  server: {
    url: 'https://corruptedly-overcured-myong.ngrok-free.dev/',
    cleartext: false
  },
  ios: {
    overrideUserAgent: 'WoundSyncApp/1.0'
  }
};

export default config;