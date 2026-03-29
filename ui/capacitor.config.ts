import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.woundsync.app',
  appName: 'WoundSync',
  webDir: 'out',
  server: {
    url: 'http://192.168.86.223:3000',
    cleartext: true
  }
};

export default config;