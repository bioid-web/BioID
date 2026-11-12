// Read-only network config for the phone viewer.
// Shadownet is the default. Mainnet is present so a deployment can be
// inspected later; it ships with no contract address and the page never
// calls it until one is set here. This file holds no keys.

export const TIP = {
  name: "bioid.tez",
  address: "tz1Tm5drMq3zueTpSonJ2FE7P3MBZN9RBNta",
  url: "https://tzkt.io/tz1Tm5drMq3zueTpSonJ2FE7P3MBZN9RBNta",
};

export const DEFAULT_NETWORK = "shadownet";

export const NETWORKS = {
  shadownet: {
    id: "shadownet",
    label: "Shadownet",
    readOnly: true,
    demo: true,
    api: "https://api.shadownet.tzkt.io/v1",
    explorer: "https://shadownet.tzkt.io",
    contract: "KT1HpDatoa5tHDctAQDY7wQgVEnrWJ9S3vix",
  },
  mainnet: {
    id: "mainnet",
    label: "Mainnet",
    readOnly: true,
    demo: false,
    api: "https://api.tzkt.io/v1",
    explorer: "https://tzkt.io",
    contract: "",
  },
};

// Tube codes on the synthetic Shadownet pilot. The label page uses these
// when TzKT cannot be reached. Live reads prefer the on-chain code index.
export const PILOT_CODES = [
  "SY00000201",
  "SY00000202",
  "SY00000203",
  "SY00000211",
  "SY00000212",
  "SY00000221",
  "SY00000222",
  "SY00000231",
  "SY00000241",
];

export function networkById(id) {
  return NETWORKS[id] || NETWORKS[DEFAULT_NETWORK];
}
