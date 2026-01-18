/**
 * Design Tokens for the Style Consistency Environment.
 *
 * This file defines the allowed design tokens for each product profile.
 * Models must use ONLY these tokens - any deviation will be penalized by the scorer.
 *
 * Structure:
 * - Colors: Tailwind color classes that are allowed
 * - Spacing: Allowed padding/margin values
 * - Radius: Allowed border-radius values
 * - Shadow: Allowed shadow values
 *
 * NOTE: The actual values will be populated by Gemini.
 * This file defines the TypeScript interface structure.
 */

export interface DesignTokens {
  /** Allowed Tailwind color classes (e.g., "gray-50", "blue-600") */
  colors: {
    /** Background colors */
    background: string[];
    /** Text colors */
    text: string[];
    /** Border colors */
    border: string[];
    /** Accent/brand colors */
    accent: string[];
    /** Status colors (success, error, warning) */
    status: string[];
  };

  /** Allowed spacing scale (Tailwind classes like "p-4", "m-2") */
  spacing: string[];

  /** Allowed border-radius values */
  radius: string[];

  /** Allowed shadow values */
  shadow: string[];

  /** Allowed font weights */
  fontWeight: string[];

  /** Allowed font sizes */
  fontSize: string[];
}

/**
 * Enterprise B2B profile tokens.
 * Low saturation, gray/white dominant, minimal gradients, strong information hierarchy.
 */
export const enterpriseTokens: DesignTokens = {
  colors: {
    background: [
      "bg-white",
      "bg-gray-50",
      "bg-gray-100",
      "bg-gray-200",
      "bg-gray-900", // For footer/dark sections
      "bg-gray-950",
      "hover:bg-gray-100",
      "hover:bg-gray-200",
      "hover:bg-gray-100/50",
      "data-[state=selected]:bg-gray-100",
    ],
    text: [
      "text-gray-950",
      "text-gray-900",
      "text-gray-700",
      "text-gray-600",
      "text-gray-500",
      "text-gray-400",
      "text-white",
      "text-gray-50",
      "placeholder:text-gray-500",
    ],
    border: [
      "border-gray-200",
      "border-gray-300",
      "border-gray-400",
      "border-transparent",
      "focus:border-blue-600",
    ],
    accent: [
      "bg-blue-600",
      "bg-blue-700",
      "text-blue-600",
      "text-blue-700",
      "border-blue-600",
      "hover:bg-blue-700",
      "focus-visible:ring-blue-600",
    ],
    status: [
      "bg-red-600",
      "hover:bg-red-700",
      "text-red-600",
      "bg-green-600",
      "hover:bg-green-700",
      "text-green-600",
      "bg-yellow-600",
      "text-yellow-600",
    ],
  },
  spacing: [
    "p-0",
    "p-1",
    "p-2",
    "p-3",
    "p-4",
    "p-6",
    "p-8",
    "px-2",
    "px-2.5",
    "px-3",
    "px-4",
    "px-6",
    "px-8",
    "py-0.5",
    "py-2",
    "py-3",
    "py-4",
    "py-6",
    "py-8",
    "m-0",
    "m-1",
    "m-2",
    "m-3",
    "m-4",
    "m-6",
    "m-8",
    "m-auto",
    "mx-2",
    "mx-3",
    "mx-4",
    "mx-6",
    "mx-auto",
    "my-2",
    "my-3",
    "my-4",
    "my-6",
    "my-8",
    "gap-2",
    "gap-3",
    "gap-4",
    "gap-6",
    "gap-8",
    "space-x-2",
    "space-x-3",
    "space-x-4",
    "space-x-8",
    "space-y-0",
    "space-y-1.5",
    "space-y-2",
    "space-y-3",
    "space-y-4",
    "space-y-8",
    "mt-4",
    "mb-1",
    "mb-4",
    "mb-6",
    "pt-0",
    "pt-4",
    "pb-2",
  ],
  radius: [
    "rounded",
    "rounded-sm",
    "rounded-md",
    "rounded-lg",
    "rounded-none",
    "rounded-full",
  ],
  shadow: ["shadow-sm", "shadow", "shadow-none"],
  fontWeight: ["font-normal", "font-medium", "font-semibold", "font-bold"],
  fontSize: [
    "text-xs",
    "text-sm",
    "text-base",
    "text-lg",
    "text-xl",
    "text-2xl",
    "text-3xl",
  ],
};

/**
 * Consumer App profile tokens.
 * Can be more vibrant, but still constrained by tokens.
 */
export const consumerTokens: DesignTokens = {
  colors: {
    background: [
      "bg-white",
      "bg-gray-50",
      "bg-gray-100",
      "bg-slate-50",
      "bg-slate-100",
      "bg-gray-900",
      "bg-gray-950",
      "hover:bg-gray-100",
      "hover:bg-slate-100",
    ],
    text: [
      "text-gray-950",
      "text-gray-900",
      "text-gray-800",
      "text-gray-700",
      "text-gray-600",
      "text-gray-500",
      "text-white",
      "text-slate-900",
      "text-slate-700",
      "text-slate-600",
      "text-gray-50",
      "placeholder:text-gray-500",
    ],
    border: [
      "border-gray-200",
      "border-gray-300",
      "border-slate-200",
      "border-slate-300",
      "border-transparent",
      "focus:border-indigo-600",
    ],
    accent: [
      "bg-indigo-600",
      "bg-indigo-700",
      "bg-emerald-600",
      "text-indigo-600",
      "text-emerald-600",
      "border-indigo-600",
      "hover:bg-indigo-700",
      "hover:bg-emerald-700",
      "focus-visible:ring-indigo-600",
    ],
    status: [
      "bg-red-600",
      "hover:bg-red-700",
      "text-red-600",
      "bg-green-600",
      "hover:bg-green-700",
      "text-green-600",
    ],
  },
  spacing: [
    "p-0",
    "p-1",
    "p-2",
    "p-3",
    "p-4",
    "p-5",
    "p-6",
    "p-8",
    "px-2",
    "px-2.5",
    "px-3",
    "px-4",
    "px-5",
    "px-6",
    "px-8",
    "py-0.5",
    "py-2",
    "py-3",
    "py-4",
    "py-5",
    "py-6",
    "m-0",
    "m-1",
    "m-2",
    "m-3",
    "m-4",
    "m-5",
    "m-6",
    "m-8",
    "m-auto",
    "mx-2",
    "mx-3",
    "mx-4",
    "mx-auto",
    "my-2",
    "my-3",
    "my-4",
    "my-6",
    "gap-2",
    "gap-3",
    "gap-4",
    "gap-5",
    "gap-6",
    "gap-8",
    "space-x-2",
    "space-x-3",
    "space-x-4",
    "space-y-0",
    "space-y-1.5",
    "space-y-2",
    "space-y-3",
    "space-y-4",
    "space-y-6",
    "space-y-8",
    "mt-4",
    "mb-1",
    "mb-4",
    "mb-6",
    "pt-0",
    "pt-4",
    "pb-2",
  ],
  radius: [
    "rounded",
    "rounded-md",
    "rounded-lg",
    "rounded-xl",
    "rounded-2xl",
    "rounded-full",
    "rounded-none",
  ],
  shadow: ["shadow-sm", "shadow", "shadow-md", "shadow-lg", "shadow-none"],
  fontWeight: ["font-normal", "font-medium", "font-semibold", "font-bold"],
  fontSize: [
    "text-xs",
    "text-sm",
    "text-base",
    "text-lg",
    "text-xl",
    "text-2xl",
    "text-3xl",
    "text-4xl",
  ],
};

/**
 * Get tokens for a specific profile.
 */
export function getTokensForProfile(
  profile: "enterprise" | "consumer"
): DesignTokens {
  switch (profile) {
    case "enterprise":
      return enterpriseTokens;
    case "consumer":
      return consumerTokens;
    default:
      return enterpriseTokens;
  }
}

/**
 * Get all allowed values as a flat set for validation.
 */
export function getAllAllowedClasses(tokens: DesignTokens): Set<string> {
  const allowed = new Set<string>();

  // Add all color classes
  Object.values(tokens.colors)
    .flat()
    .forEach((c) => allowed.add(c));

  // Add all other token types
  tokens.spacing.forEach((s) => allowed.add(s));
  tokens.radius.forEach((r) => allowed.add(r));
  tokens.shadow.forEach((s) => allowed.add(s));
  tokens.fontWeight.forEach((fw) => allowed.add(fw));
  tokens.fontSize.forEach((fs) => allowed.add(fs));

  return allowed;
}
