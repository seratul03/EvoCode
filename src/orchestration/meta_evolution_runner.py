import os
import json
from typing import TYPE_CHECKING

from src.clone_manager import CloneManager
from src.arena import ArenaReferee
from src.guarded_selection import SelectionDecision
from src.memory_manager import MemoryManager, EvolutionEvent

if TYPE_CHECKING:
    from src.evoflow import EvoFlowOrchestrator

class MetaEvolutionRunner:
    def __init__(self, orchestrator: 'EvoFlowOrchestrator'):
        self.orchestrator = orchestrator

    async def trigger_evolution(self, agent_id: str, reason: dict, current_genome):
        print(f"  [HypothesisEngine] Formulating hypothesis for {agent_id}...")
        hypothesis = await self.orchestrator.hypothesis_engine.generate_hypothesis(agent_id, reason, current_genome)
        print(f"  [HypothesisEngine] Output: {hypothesis}")
        reason["hypothesis_data"] = hypothesis

        try:
            clone = CloneManager.create_candidate(agent_id, current_genome, hypothesis)
            print(f"  [CloneManager] Candidate '{clone.candidate_id}' created. Diff: {list(clone.diff.keys())}")

            promoted = CloneManager.commit_candidate(clone, verifier=self.orchestrator.candidate_verifier)
            verification = clone.workspace_path
            
            meta_path = os.path.join(clone.workspace_path, "metadata.json")
            verification_data = {}
            if os.path.exists(meta_path):
                with open(meta_path) as _f:
                    verification_data = json.load(_f).get("verification", {})

            reason["candidate"] = {
                "candidate_id": clone.candidate_id,
                "workspace": clone.workspace_path,
                "parent_hash": clone.parent_hash,
                "candidate_hash": clone.candidate_hash,
                "diff": clone.diff,
                "verification": verification_data,
                "promoted": promoted is not None,
            }
            if promoted:
                print(f"  [Verifier] Candidate '{clone.candidate_id}' PASSED all stages. Staged for arena.")
                print(f"  [Arena] Refereeing competition between {clone.parent_hash[:8]} and {clone.candidate_hash[:8]} at Pressure Level {self.orchestrator.environment.profile.level}...")
                arena = ArenaReferee()
                arena_result = arena.compare(
                    clone.parent_genome,
                    clone.candidate_genome,
                    env_profile=self.orchestrator.environment.profile
                )
                print(f"  [Arena] Winner: {arena_result.winner.upper()} (Margin: {arena_result.margin:.4f})")
                reason["candidate"]["arena_result"] = arena_result.to_dict()
                
                decision, decision_reason = self.orchestrator.guarded_selector.evaluate(arena_result)
                print(f"  [GuardedSelection] Decision: {decision.name} - {decision_reason}")
                reason["candidate"]["selection_decision"] = decision.name
                reason["candidate"]["selection_reason"] = decision_reason
                
                if decision == SelectionDecision.PROMOTE:
                    if self.orchestrator.population.is_duplicate(clone.candidate_hash):
                        print(f"  [Population] Candidate '{clone.candidate_id}' is a duplicate. Discarding to maintain diversity.")
                        CloneManager.discard_candidate(clone)
                        decision_reason += " (Discarded by PopulationManager: Duplicate)"
                    else:
                        print(f"  [EvoFlow] Promoting candidate '{clone.candidate_id}' to a new agent in the population!")
                        new_agent_id = CloneManager.fork_to_new_agent(clone)
                        self.orchestrator.population.register_agent(new_agent_id, clone.candidate_hash)
                        
                        mock_scores = {aid: arena_result.parent_score for aid in self.orchestrator.population.active_agents}
                        mock_scores[new_agent_id] = arena_result.candidate_score
                        
                        self.orchestrator.population.enforce_population_limit(mock_scores)
                        print(f"  [Population] Spawned {new_agent_id}. Active agents: {len(self.orchestrator.population.active_agents)}")
                        
                        self.orchestrator.environment.evaluate_pressure(mock_scores)
                else:
                    print(f"  [EvoFlow] Discarding candidate '{clone.candidate_id}'.")
                    CloneManager.discard_candidate(clone)
                    
                verification_data = {}
                if os.path.exists(meta_path):
                    with open(meta_path) as _f:
                        verification_data = json.load(_f).get("verification", {})
                
                event = EvolutionEvent.create(
                    agent_id=agent_id,
                    generation=0,
                    trigger_data=reason,
                    hypothesis_data=hypothesis,
                    parent_hash=clone.parent_hash,
                    candidate_hash=clone.candidate_hash,
                    diff=clone.diff,
                    verification_result=verification_data,
                    arena_result=arena_result.to_dict(),
                    selection_decision=decision.name,
                    selection_reason=decision_reason
                )
                MemoryManager.record_event(event)
                print(f"  [Memory] Evolution event '{event.event_id}' recorded.")
                
            else:
                print(f"  [Verifier] Candidate '{clone.candidate_id}' failed verification. Discarded.")
                CloneManager.discard_candidate(clone)

        except Exception as e:
            print(f"  [CloneManager] Error during cloning/mutation: {e}")
            import traceback
            traceback.print_exc()
            raise e
