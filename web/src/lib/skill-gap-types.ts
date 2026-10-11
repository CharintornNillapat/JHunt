// web/src/lib/skill-gap-types.ts
/**
 * Strict TypeScript contracts for Skill Gap Matcher & ROI Career Engine.
 * Shared between Server Actions/APIs and Client Components.
 */

export interface SkillGapRequest {
  userSkills: string[];
}

export interface RecommendedSkill {
  name: string;
  coOccurrenceCount: number;
  coOccurrenceRate: number; // % of user's matched jobs requiring this skill
  unlockJobsCount: number;
  unlockPercentage: number; // % additional market reach unlocked
  avgSalary?: number; // Average disclosed compensation in THB/mo if available
}

export interface MatchedBlueprint {
  id: number;
  title: string;
  role: string;
  difficulty: string;
  domain: string;
  techStack: string[];
  matchedSkills: string[];
  missingSkills: string[];
  matchPercentage: number;
}

export interface SkillGapResponse {
  userSkills: string[];
  totalTechJobs: number;
  matchedJobsCount: number;
  coverageRate: number; // 0 - 100
  recommendedSkills: RecommendedSkill[];
  relevantBlueprints: MatchedBlueprint[];
  popularSuggestions: string[];
}
