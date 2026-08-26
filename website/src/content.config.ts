import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const articles = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/articles" }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    category: z.enum(["Vegas Loop", "Nashville", "Machines", "Projects", "Company"]),
    image: z.string().optional(),
    featured: z.boolean().default(false),
    hasVideo: z.boolean().default(false),
    sourceUrl: z.string().url().optional(),
    sourceName: z.string().optional(),
  }),
});

export const collections = { articles };
