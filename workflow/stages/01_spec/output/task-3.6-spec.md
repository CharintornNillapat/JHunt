# Plan: Task 3.6: OpenGraph Social Metadata, Dynamic Titles & Web Manifest across web/src/app

**Date:** 2026-10-14  
**Task ID:** 3.6  
**Reference:** `docs/contexts/task-ledger.md` (Phase 3), `AGENTS.md` (Definitions & Invariants), `antislop` Skill Suite (Mode 1 DURING)

---

## Goal
Establish comprehensive, production-grade OpenGraph social sharing metadata, dynamic title templates, Viewport configuration, and a W3C Web Manifest across the Next.js App Router (`web/src/app/`), including robots and dynamic sitemap generation, strictly enforcing antislop Mode 1 (DURING) and WCAG AA standards.

---

## antislop & UX Protocol (Mode 1: DURING)

This specification strictly adheres to the `antislop` suite (`antislop`, `antislop-ui`, `antislop-layoutmobile`, `antislop-human`, `antislop-copywriting`, `antislop-code`):

1. **R-02 (Copywriting)**:
   - Zero em dashes (`—`) anywhere in metadata titles, social share descriptions, manifest names, or SEO microcopy.
   - Use colons, pipes, commas, periods, or parentheses instead.
2. **R-03 (Mobile Responsiveness & Progressive Web Experience)**:
   - Implement Next.js 16 `Viewport` configuration (`themeColor: "#08080a"`, `colorScheme: "dark"`, `width: "device-width"`, `initialScale: 1`).
   - Web manifest must define `display: "standalone"`, `background_color: "#08080a"`, and `theme_color: "#06b6d4"` matching the obsidian dark palette.
3. **R-25 (Visual Hierarchy & Consistency)**:
   - Brand color tokens (`#08080a`, `#06b6d4`, `#0d0e12`) aligned consistently across browser chrome theme colors and manifest definitions.
4. **R-26 (Functional Endpoints & Zero Dead Links)**:
   - Next.js metadata routes (`/manifest.webmanifest`, `/robots.txt`, `/sitemap.xml`) must render valid, standard-compliant XML and JSON output.
   - Dynamic sitemap queries `getAllProjects()` safely with error boundaries, ensuring crawler discoverability without crashing.
5. **R-27 (UI & Fallback States)**:
   - Dynamic `generateMetadata` on `/blueprints/[id]` must handle missing/null projects gracefully with a clean fallback title (`Blueprint Not Found | JHunt`).
6. **R-32 (Screen Reader & Accessible Document Titles)**:
   - Distinct, descriptive page titles for every route (`%s | JHunt`) ensuring screen readers announce page transitions immediately and accurately.
7. **R-35 (Craftsmanship Verification)**:
   - Verified via `npm run build` (Turbopack SSG page and route generation) and `npm run lint`.

---

## Current Behavior (Evidence)

1. **Static Root Metadata Only (`web/src/app/layout.tsx:16-20`)**:
   - `layout.tsx` only defines a static title (`"JHunt | Market Intelligence & AI Blueprint Hub"`) and a basic description.
   - No `title.template` (`%s | JHunt`) is defined, meaning subpages either overwrite the title completely or display generic browser tab titles.
   - Missing `metadataBase`, `keywords`, `authors`, `creator`, `publisher`, and `robots` config.
   - Missing OpenGraph (`og:title`, `og:description`, `og:type`, `og:site_name`, `og:url`) and Twitter Card (`twitter:card`, `twitter:title`, `twitter:description`) tags.

2. **Missing Page-Level Metadata on Main Routes**:
   - `web/src/app/page.tsx` exports no `metadata`, leaving the home page with default root layout copy.
   - `web/src/app/analytics/page.tsx` exports no `metadata`, leaving the analytics dashboard without a dedicated title or OpenGraph preview card.

3. **Incomplete Blueprint Dynamic Metadata (`web/src/app/blueprints/[id]/page.tsx:16-28`)**:
   - `generateMetadata` returns only `title` and `description`.
   - Missing `openGraph` article tags (published time, tags/tech stack, author), and missing `twitter` card configurations.

4. **Missing Web Manifest & Crawler Endpoints**:
   - No `manifest.ts` or `manifest.json` exists in `web/src/app/`. PWA installability, mobile home screen bookmarks, and modern browser chrome color integration are absent.
   - No `robots.ts` or `sitemap.ts` exists to guide search indexing.

---

## Changes

### 1. Root Layout Metadata & Viewport Architecture
- **File**: `web/src/app/layout.tsx`
- **Viewport Configuration**:
  ```typescript
  import type { Metadata, Viewport } from "next";

  export const viewport: Viewport = {
    themeColor: "#08080a",
    colorScheme: "dark",
    width: "device-width",
    initialScale: 1,
  };
  ```
- **Root Metadata Definition**:
  ```typescript
  export const metadata: Metadata = {
    metadataBase: new URL(
      process.env.NEXT_PUBLIC_APP_URL || "https://jhunt.vercel.app"
    ),
    title: {
      default: "JHunt: Thailand Tech Market Intelligence & AI Blueprint Hub",
      template: "%s | JHunt",
    },
    description:
      "Production portfolio architecture specifications reverse-engineered from live Thailand tech demand signals across JobsDB, Blognone, and JobThai.",
    keywords: [
      "Thailand tech jobs",
      "Bangkok software engineering",
      "tech stack demand",
      "system architecture blueprints",
      "portfolio specs",
      "salary benchmarks Thailand",
    ],
    authors: [{ name: "JHunt Telemetry Engine" }],
    creator: "JHunt",
    publisher: "JHunt",
    robots: {
      index: true,
      follow: true,
    },
    openGraph: {
      type: "website",
      locale: "en_US",
      url: "/",
      siteName: "JHunt",
      title: "JHunt: Thailand Tech Market Intelligence & AI Blueprint Hub",
      description:
        "Production portfolio architecture specifications reverse-engineered from live Thailand tech demand signals.",
    },
    twitter: {
      card: "summary_large_image",
      title: "JHunt: Thailand Tech Market Intelligence & AI Blueprint Hub",
      description:
        "Production portfolio architecture specifications reverse-engineered from live Thailand tech demand signals.",
    },
  };
  ```

### 2. Home Page Metadata
- **File**: `web/src/app/page.tsx`
- **Metadata Export**:
  ```typescript
  import type { Metadata } from "next";

  export const metadata: Metadata = {
    title: "Portfolio Architecture Blueprints",
    description:
      "Production-grade systems reverse-engineered from active engineering requirements in Thailand. Explore verifiable architecture specifications with concurrency, persistence, and distributed systems solutions.",
    openGraph: {
      title: "Portfolio Architecture Blueprints | JHunt",
      description:
        "Production-grade systems reverse-engineered from active engineering requirements in Thailand.",
      url: "/",
    },
  };
  ```

### 3. Analytics Page Metadata
- **File**: `web/src/app/analytics/page.tsx`
- **Metadata Export**:
  ```typescript
  import type { Metadata } from "next";

  export const metadata: Metadata = {
    title: "Market Intelligence & Tech Cluster Index",
    description:
      "Empirical frequency distributions, compensation benchmarks, and cloud market share extracted from active software engineering job postings in Thailand.",
    openGraph: {
      title: "Market Intelligence & Tech Cluster Index | JHunt",
      description:
        "Empirical frequency distributions, compensation benchmarks, and cloud market share extracted from active software engineering job postings in Thailand.",
      url: "/analytics",
    },
  };
  ```

### 4. Rich Dynamic Blueprint Metadata
- **File**: `web/src/app/blueprints/[id]/page.tsx`
- **Enhanced `generateMetadata`**:
  ```typescript
  export async function generateMetadata({ params }: Props): Promise<Metadata> {
    const { id } = await params;
    const project = await getProjectById(id);
    if (!project) {
      return {
        title: "Blueprint Not Found",
        description: "The requested architecture blueprint could not be found.",
      };
    }

    const techTags = project.tech_stack
      ? project.tech_stack
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean)
      : [];
    const description = `Production portfolio architecture spec for ${project.role} in ${project.domain || "Tech"}. Features: ${techTags.slice(0, 4).join(", ") || "Production Stack"}. Difficulty: ${project.difficulty}.`;

    return {
      title: project.title,
      description,
      openGraph: {
        title: `${project.title} | JHunt Blueprint`,
        description,
        type: "article",
        publishedTime: project.created_at,
        tags: techTags,
      },
      twitter: {
        card: "summary_large_image",
        title: `${project.title} | JHunt Blueprint`,
        description,
      },
    };
  }
  ```

### 5. Web Manifest Generation
- **File**: `web/src/app/manifest.ts`
- **Metadata Route**:
  ```typescript
  import type { MetadataRoute } from "next";

  export default function manifest(): MetadataRoute.Manifest {
    return {
      name: "JHunt: Thailand Tech Market Intelligence",
      short_name: "JHunt",
      description:
        "Portfolio architecture specifications derived from live Thailand tech demand signals.",
      start_url: "/",
      display: "standalone",
      background_color: "#08080a",
      theme_color: "#06b6d4",
      icons: [
        {
          src: "/favicon.ico",
          sizes: "any",
          type: "image/x-icon",
        },
      ],
    };
  }
  ```

### 6. Search Indexing: `robots.ts` and `sitemap.ts`
- **File**: `web/src/app/robots.ts`
  ```typescript
  import type { MetadataRoute } from "next";

  export default function robots(): MetadataRoute.Robots {
    const baseUrl =
      process.env.NEXT_PUBLIC_APP_URL || "https://jhunt.vercel.app";
    return {
      rules: {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/"],
      },
      sitemap: `${baseUrl}/sitemap.xml`,
    };
  }
  ```
- **File**: `web/src/app/sitemap.ts`
  ```typescript
  import type { MetadataRoute } from "next";
  import { getAllProjects } from "@/lib/turso";

  export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
    const baseUrl =
      process.env.NEXT_PUBLIC_APP_URL || "https://jhunt.vercel.app";

    const staticRoutes: MetadataRoute.Sitemap = [
      {
        url: baseUrl,
        lastModified: new Date(),
        changeFrequency: "hourly",
        priority: 1.0,
      },
      {
        url: `${baseUrl}/analytics`,
        lastModified: new Date(),
        changeFrequency: "hourly",
        priority: 0.9,
      },
    ];

    try {
      const projects = await getAllProjects();
      const projectRoutes: MetadataRoute.Sitemap = projects.map((p) => ({
        url: `${baseUrl}/blueprints/${p.id}`,
        lastModified: p.created_at ? new Date(p.created_at) : new Date(),
        changeFrequency: "daily",
        priority: 0.8,
      }));
      return [...staticRoutes, ...projectRoutes];
    } catch {
      return staticRoutes;
    }
  }
  ```

---

## Verification Plan

1. **TypeScript & Static Analysis**:
   - `cd web; npm run lint` passes with 0 errors and 0 warnings.
   - `cd web; npm run build` compiles clean static/SSG routes including `manifest.webmanifest`, `robots.txt`, and `sitemap.xml`.
2. **Hermetic Python Test Suite**:
   - `uv run python -m unittest discover tests` passes (197 tests).
3. **antislop Copywriting & Quality Audit**:
   - Zero em dashes (`—`) across all titles, descriptions, keywords, manifest names, and metadata properties.
   - Title templating verified (`%s | JHunt` resolves as expected on subpages).
   - Valid OpenGraph schema and Twitter Card properties.
   - Error handling in `sitemap.ts` verified to gracefully return static routes if database is offline.
