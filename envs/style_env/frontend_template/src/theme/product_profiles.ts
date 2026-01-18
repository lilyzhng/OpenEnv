/**
 * Product Profile Definitions for the Style Consistency Environment.
 *
 * Each profile defines:
 * - Allowed colors (whitelist)
 * - Forbidden patterns (blacklist)
 * - Allowed spacing/radius/shadow scales
 *
 * The scorer uses these definitions to evaluate generated code.
 */

import { getTokensForProfile, type DesignTokens } from "./tokens";

export interface ForbiddenPatterns {
  /** Forbid gradient classes (bg-gradient-to-*, from-*, to-*, via-*) */
  gradients: boolean;

  /** Specific color tokens that are forbidden (e.g., "purple-500", "fuchsia-*") */
  neonColors: string[];

  /** Forbid inline styles (style={{...}}) */
  inlineStyles: boolean;

  /** Forbid raw color values (#xxx, rgb(), hsl()) */
  rawColorValues: boolean;
}

export interface ProductProfile {
  /** Profile identifier */
  name: string;

  /** Human-readable description */
  description: string;

  /** Design tokens for this profile */
  tokens: DesignTokens;

  /** Patterns that are explicitly forbidden */
  forbiddenPatterns: ForbiddenPatterns;

  /** Required UI components that must be used (from src/components/ui/) */
  requiredComponents: string[];
}

/**
 * Enterprise B2B Profile
 *
 * - Low saturation, gray/white dominant
 * - No gradients
 * - Strong information hierarchy
 * - Conservative, professional appearance
 * - Blue accents for trust and stability
 * - Rectilinear shapes (rounded-md)
 * - Subtle shadows
 */
export const enterpriseProfile: ProductProfile = {
  name: "enterprise",
  description:
    "Enterprise B2B tools: low saturation, gray/white dominant, no gradients, strong information hierarchy. Use blue accents for primary actions. Borders should be subtle gray-200. Spacing should be dense but consistent.",
  tokens: getTokensForProfile("enterprise"),
  forbiddenPatterns: {
    gradients: true,
    neonColors: [
      "purple-400",
      "purple-500",
      "purple-600",
      "fuchsia-400",
      "fuchsia-500",
      "fuchsia-600",
      "pink-400",
      "pink-500",
      "pink-600",
      "rose-400",
      "rose-500",
      "rose-600",
      "violet-400",
      "violet-500",
      "violet-600",
      "cyan-400",
      "cyan-500",
      "lime-400",
      "lime-500",
    ],
    inlineStyles: true,
    rawColorValues: true,
  },
  requiredComponents: ["Button", "Card", "Input", "Badge", "Table"],
};

/**
 * Consumer App Profile
 *
 * - Can be more vibrant than enterprise
 * - Still constrained by tokens
 * - No raw colors or inline styles
 * - Indigo/Emerald accents
 * - Softer shapes (rounded-lg, rounded-xl)
 * - More generous spacing
 */
export const consumerProfile: ProductProfile = {
  name: "consumer",
  description:
    "Consumer apps: can be more vibrant, but still token-constrained. Use indigo/emerald accents. No random flashy colors. Cards can have more shadow/elevation. Typography can be more expressive.",
  tokens: getTokensForProfile("consumer"),
  forbiddenPatterns: {
    gradients: true, // Still no gradients by default for MVP
    neonColors: [
      "fuchsia-400",
      "fuchsia-500",
      "fuchsia-600",
      "pink-400",
      "pink-500",
      "pink-600",
      "rose-400",
      "rose-500",
      "rose-600",
      "lime-400",
      "lime-500",
      "yellow-400",
      "yellow-500",
    ],
    inlineStyles: true,
    rawColorValues: true,
  },
  requiredComponents: ["Button", "Card", "Input"],
};

/**
 * All available profiles.
 */
export const profiles: Record<string, ProductProfile> = {
  enterprise: enterpriseProfile,
  consumer: consumerProfile,
};

/**
 * Get a profile by name.
 */
export function getProfile(name: string): ProductProfile | undefined {
  return profiles[name];
}

/**
 * Get profile as a machine-readable string for agent context.
 */
export function getProfileDescription(profile: ProductProfile): string {
  const lines = [
    `# Profile: ${profile.name}`,
    ``,
    `## Description`,
    profile.description,
    ``,
    `## Allowed Colors`,
    `- Background: ${profile.tokens.colors.background.join(", ")}`,
    `- Text: ${profile.tokens.colors.text.join(", ")}`,
    `- Border: ${profile.tokens.colors.border.join(", ")}`,
    `- Accent: ${profile.tokens.colors.accent.join(", ")}`,
    `- Status: ${profile.tokens.colors.status.join(", ")}`,
    ``,
    `## Allowed Spacing`,
    profile.tokens.spacing.join(", "),
    ``,
    `## Allowed Radius`,
    profile.tokens.radius.join(", "),
    ``,
    `## Allowed Shadow`,
    profile.tokens.shadow.join(", "),
    ``,
    `## Forbidden Patterns`,
    `- Gradients: ${profile.forbiddenPatterns.gradients ? "FORBIDDEN" : "allowed"}`,
    `- Inline styles: ${profile.forbiddenPatterns.inlineStyles ? "FORBIDDEN" : "allowed"}`,
    `- Raw color values (#xxx, rgb, hsl): ${profile.forbiddenPatterns.rawColorValues ? "FORBIDDEN" : "allowed"}`,
    `- Neon colors: ${profile.forbiddenPatterns.neonColors.join(", ")}`,
    ``,
    `## Required Components`,
    `Must use from src/components/ui/: ${profile.requiredComponents.join(", ")}`,
  ];

  return lines.join("\n");
}
