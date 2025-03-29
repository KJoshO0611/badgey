import discord
import logging
from typing import Union, List, Dict, Set
from config import CONFIG

logger = logging.getLogger('badgey.permissions')

# Command-specific permission overrides
# Map of command_name -> list of allowed roles
COMMAND_PERMISSIONS: Dict[str, List[str]] = {
    # Quiz creation and management
    "create_quiz": ["Admin", "Quiz Creators", "Community Managers"],
    "edit_quiz": ["Admin", "Quiz Editors", "Community Managers"],
    "delete_quiz": ["Admin", "Community Managers"],
    "add_question": ["Admin", "Quiz Creators", "Community Managers"],
    "edit_question": ["Admin", "Quiz Editors", "Community Managers"],
    
    # Quiz participation (everyone can use these)
    "take_quiz": [],
    "list_quizzes": [],
    "leaderboard": [],
    
    # Scheduled quizzes
    "schedule_quiz": ["Admin", "Event Managers", "Community Managers"],
    
    # Admin commands
    "sync": ["Admin"],
    "export_data": ["Admin"],
}

# Permission-based feature flags
FEATURES: Dict[str, List[str]] = {
    "create_quiz": ["Admin", "Quiz Creators", "Community Managers"],
    "edit_quiz": ["Admin", "Quiz Editors", "Community Managers"],
    "view_analytics": ["Admin", "Community Managers"],
    "export_data": ["Admin"],
}

def user_has_permission(user: discord.Member, command_name: str) -> bool:
    """
    Check if a user has permission to use a command
    
    Args:
        user (discord.Member): The user to check
        command_name (str): The command name to check permissions for
        
    Returns:
        bool: True if the user has permission, False otherwise
    """
    # Default to required roles if no specific permission is defined
    required_roles = COMMAND_PERMISSIONS.get(command_name, CONFIG['REQUIRED_ROLES'])
    
    # If no roles are required, allow everyone
    if not required_roles:
        return True
        
    # Check user roles
    user_roles = set(role.name for role in user.roles)
    return any(role in user_roles for role in required_roles)

def user_has_feature_access(user: discord.Member, feature: str) -> bool:
    """
    Check if a user has access to a specific feature
    
    Args:
        user (discord.Member): The user to check
        feature (str): The feature to check access for
        
    Returns:
        bool: True if the user has access, False otherwise
    """
    # Default to required roles if no specific permission is defined
    required_roles = FEATURES.get(feature, CONFIG['REQUIRED_ROLES'])
    
    # If no roles are required, allow everyone
    if not required_roles:
        return True
        
    # Check user roles
    user_roles = set(role.name for role in user.roles)
    return any(role in user_roles for role in required_roles)

def get_missing_permissions(user: discord.Member, command_name: str) -> List[str]:
    """
    Get a list of missing permissions for a user to use a command
    
    Args:
        user (discord.Member): The user to check
        command_name (str): The command name to check permissions for
        
    Returns:
        List[str]: List of missing role names (empty if user has permission)
    """
    required_roles = COMMAND_PERMISSIONS.get(command_name, CONFIG['REQUIRED_ROLES'])
    
    # If no roles are required, no permissions are missing
    if not required_roles:
        return []
        
    # Check user roles
    user_roles = set(role.name for role in user.roles)
    return [role for role in required_roles if role not in user_roles]

def log_permission_check(user: discord.Member, command_name: str, has_permission: bool):
    """
    Log a permission check (useful for auditing)
    
    Args:
        user (discord.Member): The user that was checked
        command_name (str): The command name that was checked
        has_permission (bool): Whether the user has permission
    """
    if has_permission:
        logger.debug(f"User {user.name} ({user.id}) has permission to use command {command_name}")
    else:
        # Log at info level for denied permissions (more visibility)
        missing = get_missing_permissions(user, command_name)
        logger.info(f"User {user.name} ({user.id}) lacks permission to use command {command_name}. "
                    f"Missing roles: {', '.join(missing)}") 