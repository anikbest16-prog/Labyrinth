"""Persistent social memory tracking for players."""

from __future__ import annotations

from typing import Any, Dict, List

from . import data


def initialize_social_memory(player_id: int, num_players: int = 8) -> Dict[str, List[Any]]:
    """
    Initialize social memory for a player.
    
    Each field is a list indexed by player ID (0-7).
    Index 0 is self (marked as "me").
    """
    return {
        "trust": ["me"] + [0.5] * (num_players - 1),
        "fear": ["me"] + [0.0] * (num_players - 1),
        "suspicion": ["me"] + [0.2] * (num_players - 1),
        "overall_analysis": [
            "You."
        ] + [
            "Unknown. No significant interactions yet."
        ] * (num_players - 1),
        "last_conversation": [""] + [""] * (num_players - 1),
        "promises": [
            []
        ] + [[] for _ in range(num_players - 1)],
        "estimated_role": ["me"] + ["Unknown"] * (num_players - 1),
        "estimated_role_confidence": ["N/A"] + [0.0] * (num_players - 1),
        "estimated_objective": ["me"] + ["Unknown"] * (num_players - 1),
        "estimated_objective_confidence": ["N/A"] + [0.0] * (num_players - 1),
    }


def update_social_memory_from_action(
    social_memory: Dict[str, List[Any]],
    player_id: int,
    action_type: str,
    target_player_id: int,
    action_details: str,
) -> None:
    """
    Update social memory based on a player's action.
    
    This is called after a player takes an action involving another player.
    """
    if target_player_id < 0 or target_player_id >= len(social_memory["trust"]):
        return
    
    # Adjust metrics based on action type
    if action_type == "attack":
        social_memory["fear"][target_player_id] = min(
            1.0, social_memory["fear"][target_player_id] + 0.3
        )
        social_memory["trust"][target_player_id] = max(
            0.0, social_memory["trust"][target_player_id] - 0.4
        )
        social_memory["suspicion"][target_player_id] = min(
            1.0, social_memory["suspicion"][target_player_id] + 0.2
        )
        social_memory["last_conversation"][target_player_id] = f"Attacked me."
    
    elif action_type == "trade":
        social_memory["trust"][target_player_id] = min(
            1.0, social_memory["trust"][target_player_id] + 0.2
        )
        social_memory["fear"][target_player_id] = max(
            0.0, social_memory["fear"][target_player_id] - 0.1
        )
        social_memory["last_conversation"][target_player_id] = (
            f"Traded items with me. {action_details}"
        )
    
    elif action_type == "conversation":
        social_memory["suspicion"][target_player_id] = max(
            0.0, social_memory["suspicion"][target_player_id] - 0.1
        )
        social_memory["last_conversation"][target_player_id] = action_details
    
    elif action_type == "shared_location":
        # Just being in same location builds slight trust
        if social_memory["trust"][target_player_id] < 0.5:
            social_memory["trust"][target_player_id] += 0.05


def update_estimated_role(
    social_memory: Dict[str, List[Any]],
    about_player_id: int,
    role_name: str,
    confidence: float = 0.8,
) -> None:
    """Update estimated role for another player."""
    if about_player_id >= len(social_memory["estimated_role"]):
        return
    
    # Validate role exists
    valid_roles = list(data.ROLES.keys())
    if role_name not in valid_roles and role_name != "Unknown":
        role_name = "Unknown"
        confidence = 0.0
    
    social_memory["estimated_role"][about_player_id] = role_name
    social_memory["estimated_role_confidence"][about_player_id] = max(
        0.0, min(1.0, confidence)
    )


def update_estimated_objective(
    social_memory: Dict[str, List[Any]],
    about_player_id: int,
    objective_name: str,
    confidence: float = 0.8,
) -> None:
    """Update estimated objective for another player."""
    if about_player_id >= len(social_memory["estimated_objective"]):
        return
    
    # Validate objective exists
    valid_objectives = list(data.OBJECTIVES.values())
    if objective_name not in valid_objectives and objective_name != "Unknown":
        objective_name = "Unknown"
        confidence = 0.0
    
    social_memory["estimated_objective"][about_player_id] = objective_name
    social_memory["estimated_objective_confidence"][about_player_id] = max(
        0.0, min(1.0, confidence)
    )


def add_promise(
    social_memory: Dict[str, List[Any]],
    from_player_id: int,
    promise_text: str,
) -> None:
    """Record a promise made by another player."""
    if from_player_id >= len(social_memory["promises"]):
        return
    
    if promise_text not in social_memory["promises"][from_player_id]:
        social_memory["promises"][from_player_id].append(promise_text)


def remove_promise(
    social_memory: Dict[str, List[Any]],
    from_player_id: int,
    promise_text: str,
) -> None:
    """Remove a promise (e.g., if broken or fulfilled)."""
    if from_player_id >= len(social_memory["promises"]):
        return
    
    if promise_text in social_memory["promises"][from_player_id]:
        social_memory["promises"][from_player_id].remove(promise_text)


def parse_social_memory_update(
    action_text: str,
    social_memory: Dict[str, List[Any]],
) -> None:
    """
    Parse SOCIAL_MEMORY_UPDATE directives from an AI's action response.
    
    Expected format in action response:
    
    SOCIAL_MEMORY_UPDATE
    Player X:
      trust: 0.65
      fear: 0.1
      suspicion: 0.3
      overall_analysis: "Clear, honest player..."
      last_conversation: "Offered to trade supplies"
      promises: ["Will help search Vault", "Won't attack"]
      estimated_role: "Investigator"
      estimated_role_confidence: 0.7
      estimated_objective: "Recover Drive A"
      estimated_objective_confidence: 0.6
    """
    if "SOCIAL_MEMORY_UPDATE" not in action_text:
        return
    
    import re
    
    # Find the social memory update section
    update_section = action_text.split("SOCIAL_MEMORY_UPDATE")[1]
    
    # Parse each Player X: block
    player_blocks = re.findall(r"Player\s+(\d+):(.*?)(?=Player\s+\d+:|$)", update_section, re.DOTALL)
    
    for player_num_str, block_content in player_blocks:
        try:
            player_idx = int(player_num_str)
            if player_idx < 1 or player_idx > len(social_memory["trust"]):
                continue
            
            player_idx -= 1  # Convert to 0-indexed
            
            # Parse individual fields
            lines = block_content.strip().split("\n")
            for line in lines:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == "trust":
                    try:
                        social_memory["trust"][player_idx] = float(value)
                    except ValueError:
                        pass
                
                elif key == "fear":
                    try:
                        social_memory["fear"][player_idx] = float(value)
                    except ValueError:
                        pass
                
                elif key == "suspicion":
                    try:
                        social_memory["suspicion"][player_idx] = float(value)
                    except ValueError:
                        pass
                
                elif key == "overall_analysis":
                    social_memory["overall_analysis"][player_idx] = value.strip('"\'')
                
                elif key == "last_conversation":
                    social_memory["last_conversation"][player_idx] = value.strip('"\'')
                
                elif key == "promises":
                    # Parse list of promises
                    try:
                        import ast
                        promises_list = ast.literal_eval(value)
                        if isinstance(promises_list, list):
                            social_memory["promises"][player_idx] = promises_list
                    except (ValueError, SyntaxError):
                        pass
                
                elif key == "estimated_role":
                    role_val = value.strip('"\'')
                    valid_roles = list(data.ROLES.keys())
                    if role_val in valid_roles or role_val == "Unknown":
                        social_memory["estimated_role"][player_idx] = role_val
                
                elif key == "estimated_role_confidence":
                    try:
                        social_memory["estimated_role_confidence"][player_idx] = float(value)
                    except ValueError:
                        pass
                
                elif key == "estimated_objective":
                    obj_val = value.strip('"\'')
                    valid_objectives = list(data.OBJECTIVES.values())
                    if obj_val in valid_objectives or obj_val == "Unknown":
                        social_memory["estimated_objective"][player_idx] = obj_val
                
                elif key == "estimated_objective_confidence":
                    try:
                        social_memory["estimated_objective_confidence"][player_idx] = float(value)
                    except ValueError:
                        pass
        
        except (ValueError, IndexError):
            pass


def format_social_memory_for_perception(
    social_memory: Dict[str, List[Any]],
    num_players: int = 8,
) -> str:
    """
    Format social memory as a readable string for the perception payload.
    """
    lines = ["SOCIAL MEMORY"]
    lines.append("=" * 60)
    
    for player_idx in range(num_players):
        lines.append("")
        if player_idx == 0:
            lines.append("Player 1 (You)")
        else:
            lines.append(f"Player {player_idx + 1}")
        lines.append("-" * 40)
        
        # Trust, Fear, Suspicion
        trust_val = social_memory["trust"][player_idx]
        if trust_val != "me":
            lines.append(f"  Trust:      {trust_val:.2f}")
        
        fear_val = social_memory["fear"][player_idx]
        if fear_val != "me":
            lines.append(f"  Fear:       {fear_val:.2f}")
        
        suspicion_val = social_memory["suspicion"][player_idx]
        if suspicion_val != "me":
            lines.append(f"  Suspicion:  {suspicion_val:.2f}")
        
        # Overall Analysis
        analysis = social_memory["overall_analysis"][player_idx]
        if analysis:
            lines.append(f"  Overall Analysis:")
            for line in analysis.split("\n"):
                lines.append(f"    {line}")
        
        # Last Conversation
        last_conv = social_memory["last_conversation"][player_idx]
        if last_conv:
            lines.append(f"  Last Conversation:")
            lines.append(f"    {last_conv}")
        
        # Promises
        promises = social_memory["promises"][player_idx]
        if promises:
            lines.append(f"  Promises:")
            for promise in promises:
                lines.append(f"    - {promise}")
        
        # Estimated Role
        role = social_memory["estimated_role"][player_idx]
        role_conf = social_memory["estimated_role_confidence"][player_idx]
        if role and role != "me":
            lines.append(
                f"  Estimated Role: {role} "
                f"(confidence: {role_conf:.1%})"
            )
        
        # Estimated Objective
        obj = social_memory["estimated_objective"][player_idx]
        obj_conf = social_memory["estimated_objective_confidence"][player_idx]
        if obj and obj != "me":
            lines.append(
                f"  Estimated Objective: {obj} "
                f"(confidence: {obj_conf:.1%})"
            )
    
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)
