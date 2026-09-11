import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: "https://www.tunnelati.com",
  trailingSlash: "never",
  integrations: [sitemap()],
  redirects: {
    "/articles/prufrock-autonomous-rings-2026-08-08":
      "/articles/2026-08-08-boring-company-details-prufrock-autonomous-ring-placement",
    "/articles/prufrock-autonomous-rings-2026-08-08/":
      "/articles/2026-08-08-boring-company-details-prufrock-autonomous-ring-placement",
  },
});
