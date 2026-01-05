import { GroupedResult, StrategyGroupedResult, FocusGroupMetadata, StrategyMetadata } from '../types';

export interface RaceGroup {
    raceKey: string;
    raceName: string;
    raceMetadata: {
        outcome?: string;
        margin?: number;
        year?: number;
        state?: string;
    };
    focusGroups: GroupedResult[];
    strategies: StrategyGroupedResult[];
}

/**
 * Groups focus groups and strategy memos by race for unified display.
 * This allows related content (focus groups + strategy memos for the same race)
 * to be displayed together.
 */
export function groupByRace(
    results: GroupedResult[],
    lessons: StrategyGroupedResult[]
): Record<string, RaceGroup> {
    const raceGroups: Record<string, RaceGroup> = {};

    // Helper to normalize race names for matching
    const normalizeRaceName = (name: string): string => {
        return name.toLowerCase().replace(/[^a-z0-9]/g, '');
    };

    // Group focus groups by race_name
    results.forEach(fg => {
        const raceName = fg.focus_group_metadata.race_name || 'Other';
        const raceKey = normalizeRaceName(raceName);

        if (!raceGroups[raceKey]) {
            raceGroups[raceKey] = {
                raceKey,
                raceName,
                raceMetadata: {
                    outcome: fg.focus_group_metadata.outcome,
                },
                focusGroups: [],
                strategies: [],
            };
        }
        raceGroups[raceKey].focusGroups.push(fg);
    });

    // Add strategies to their race groups
    lessons.forEach(strategy => {
        const meta = strategy.race_metadata;
        // Create race name from state + office (e.g., "Montana Senate")
        const raceName = `${meta.state || 'Unknown'} ${meta.office || ''}`.trim();
        const raceKey = normalizeRaceName(raceName);

        if (!raceGroups[raceKey]) {
            raceGroups[raceKey] = {
                raceKey,
                raceName,
                raceMetadata: {
                    outcome: meta.outcome,
                    margin: meta.margin,
                    year: meta.year,
                    state: meta.state,
                },
                focusGroups: [],
                strategies: [],
            };
        } else {
            // Merge metadata from strategy if it has more details
            if (meta.margin !== undefined) {
                raceGroups[raceKey].raceMetadata.margin = meta.margin;
            }
            if (meta.year !== undefined) {
                raceGroups[raceKey].raceMetadata.year = meta.year;
            }
            if (meta.state) {
                raceGroups[raceKey].raceMetadata.state = meta.state;
            }
        }
        raceGroups[raceKey].strategies.push(strategy);
    });

    return raceGroups;
}

/**
 * Returns race groups sorted by relevance:
 * - Groups with both strategies and focus groups first
 * - Then by number of focus groups (descending)
 * - Then alphabetically by race name
 */
export function getSortedRaceGroups(raceGroups: Record<string, RaceGroup>): RaceGroup[] {
    return Object.values(raceGroups).sort((a, b) => {
        // Prioritize races with both content types
        const aHasBoth = a.strategies.length > 0 && a.focusGroups.length > 0;
        const bHasBoth = b.strategies.length > 0 && b.focusGroups.length > 0;
        if (aHasBoth && !bHasBoth) return -1;
        if (bHasBoth && !aHasBoth) return 1;

        // Then by total content volume
        const aTotal = a.focusGroups.length + a.strategies.length;
        const bTotal = b.focusGroups.length + b.strategies.length;
        if (aTotal !== bTotal) return bTotal - aTotal;

        // Finally alphabetically
        return a.raceName.localeCompare(b.raceName);
    });
}
