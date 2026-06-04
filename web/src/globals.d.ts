interface OpsPilotConfig {
  apiUrl: string;
  clientId: string;
  cognitoDomain: string;
  logoutUri: string;
  redirectUri: string;
  scopes: string[];
}

interface Window {
  OPSPILOT_CONFIG: OpsPilotConfig;
}
