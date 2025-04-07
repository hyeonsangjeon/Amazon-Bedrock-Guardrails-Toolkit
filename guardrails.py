import boto3
import json
import time
import os

# AWS Region Setting
AWS_REGION = "us-east-1"  # Change to the region you want to use (e.g., us-east-1, ap-northeast-2, etc.)

# Load Configuration File
def load_guardrail_config(config_file="guardrail_config.json"):
    """
    Loads the guardrail configuration file.
    
    :param config_file: Configuration file path
    :return: Configuration dictionary
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"Successfully loaded guardrail configuration file '{config_file}'.")
        return config
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in configuration file '{config_file}'.")
        return {}

def create_dynamic_guardrail(
    role_name, 
    user_id, 
    check_harmful_content=True, 
    check_prompt_attacks=True, 
    custom_denied_topics=None,
    config_file="guardrail_config.json",
    region=AWS_REGION
):
    """
    Dynamically creates a guardrail based on role settings in the configuration file
    
    :param role_name: Role name defined in the configuration file
    :param user_id: User identifier
    :param check_harmful_content: Whether to enable harmful content filter
    :param check_prompt_attacks: Whether to enable prompt attack prevention
    :param custom_denied_topics: Additional list of denied topics (added to default settings)
    :param config_file: Guardrail configuration file path
    :param region: AWS region
    :return: Created guardrail ID
    """
    # Create Bedrock client
    bedrock_client = boto3.client('bedrock', region_name=region)
    
    # Load configuration file
    config = load_guardrail_config(config_file)
    
    # Initialize default settings
    content_filter_level = "MEDIUM"
    blocked_topics = []
    block_message = f"Access is restricted with {role_name} permissions."
    blocked_input_message = f"This input is not allowed with {role_name} permissions."
    enable_profanity_filter = True
    custom_denied_words = []
    
    # Load configuration for the role name if it exists
    if config and role_name in config:
        role_config = config[role_name]
        content_filter_level = role_config.get('content_filter_level', content_filter_level)
        blocked_topics = role_config.get('blocked_topics', blocked_topics)
        block_message = role_config.get('block_message', block_message)
        blocked_input_message = role_config.get('blocked_input_message', blocked_input_message)
        enable_profanity_filter = role_config.get('enable_profanity_filter', enable_profanity_filter)
        custom_denied_words = role_config.get('denied_words', custom_denied_words)
        
        print(f"Loaded '{role_name}' role settings from configuration file.")
    else:
        print(f"Warning: Could not find settings for '{role_name}' role. Using default settings.")
    
    # Handle additional denied topics
    if custom_denied_topics:
        for topic in custom_denied_topics:
            if isinstance(topic, dict) and 'name' in topic and 'definition' in topic:
                # Check if topic already exists
                existing = False
                for existing_topic in blocked_topics:
                    if isinstance(existing_topic, dict) and existing_topic.get('name') == topic['name']:
                        existing = True
                        break
                
                if not existing:
                    blocked_topics.append(topic)
    
    # Log filter status
    print(f"\n=== Configuration for {role_name} ===")
    print(f"- Content filter level: {content_filter_level}")
    print(f"- Harmful content filter: {'Enabled' if check_harmful_content else 'Disabled'}")
    print(f"- Prompt attack prevention: {'Enabled' if check_prompt_attacks else 'Disabled'}")
    print(f"- Profanity filter: {'Enabled' if enable_profanity_filter else 'Disabled'}")
    
    # Log topic policy
    if blocked_topics:
        print(f"- Blocked topics: {len(blocked_topics)}")
        for topic in blocked_topics:
            name = topic['name'] if isinstance(topic, dict) else topic
            definition = topic.get('definition', 'No definition') if isinstance(topic, dict) else f"Topics related to {topic}"
            print(f"  • {name}: {definition}")
    else:
        print("- No blocked topics")
    
    # Log custom words
    if custom_denied_words:
        print(f"- Denied words: {len(custom_denied_words)}")
        for word in custom_denied_words:
            masked_word = word[0] + '*' * (len(word) - 2) + word[-1] if len(word) > 2 else word
            print(f"  • {masked_word}")
    else:
        print("- No denied words")
    
    # Configure topic policy - standardize topic format
    topics_config = []
    for topic in blocked_topics:
        if isinstance(topic, dict):
            topics_config.append({
                "name": topic['name'],
                "definition": topic.get('definition', f"Topics related to {topic['name']}"),
                "type": "DENY"
            })
        else:
            topics_config.append({
                "name": topic,
                "definition": f"Topics related to {topic}",
                "type": "DENY"
            })
    
    # Configure content policy filters
    filters_config = []
    if check_harmful_content:
        filters_config.extend([
            {
                "type": "SEXUAL", 
                "inputStrength": content_filter_level,
                "outputStrength": content_filter_level
            },
            {
                "type": "VIOLENCE", 
                "inputStrength": content_filter_level,
                "outputStrength": content_filter_level
            },
            {
                "type": "HATE", 
                "inputStrength": content_filter_level,
                "outputStrength": content_filter_level
            },
            {
                "type": "INSULTS", 
                "inputStrength": content_filter_level,
                "outputStrength": content_filter_level
            },
            {
                "type": "MISCONDUCT", 
                "inputStrength": content_filter_level,
                "outputStrength": content_filter_level
            }
        ])
    
    # Configure prompt attack prevention settings
    if check_prompt_attacks:
        filters_config.append({
            "type": "PROMPT_ATTACK",
            "inputStrength": content_filter_level,
            "outputStrength": "NONE"  # Do not apply prompt attack filter to outputs
        })
    
    # Configure word policy
    words_config = []
    for word in custom_denied_words:
        words_config.append({
            "text": word
        })
    
    # Configure managed word lists
    managed_word_lists_config = []
    if enable_profanity_filter:
        managed_word_lists_config.append({
            "type": "PROFANITY"
        })
    
    # Change tag format (convert dictionary to list)
    tags_list = [
        {"key": "RoleName", "value": role_name},
        {"key": "UserId", "value": user_id},
        {"key": "HarmfulContentFilter", "value": str(check_harmful_content)},
        {"key": "PromptAttackPrevention", "value": str(check_prompt_attacks)},
        {"key": "ProfanityFilter", "value": str(enable_profanity_filter)},
        {"key": "BlockedTopics", "value": str(len(topics_config))},
        {"key": "DeniedWords", "value": str(len(words_config))},
        {"key": "CreatedAt", "value": time.strftime("%Y-%m-%d %H:%M:%S")}
    ]
    
    # Create guardrail (adjusted for new API structure)
    try:
        create_params = {
            "name": f"Guardrail-{role_name}-{user_id}",
            "description": f"Dynamically generated guardrail for {role_name}",
            "blockedInputMessaging": blocked_input_message,
            "blockedOutputsMessaging": block_message,
            "tags": tags_list,
            "clientRequestToken": f"{role_name}-{user_id}-{int(time.time())}"
        }
        
        # Add topic policy only if topics are configured
        if topics_config:
            create_params["topicPolicyConfig"] = {
                "topicsConfig": topics_config
            }
        
        # Add content filters only if filters are configured
        if filters_config:
            create_params["contentPolicyConfig"] = {
                "filtersConfig": filters_config
            }
        
        # Add word policy configuration
        word_policy = {}
        if words_config:
            word_policy["wordsConfig"] = words_config
        
        if managed_word_lists_config:
            word_policy["managedWordListsConfig"] = managed_word_lists_config
        
        if word_policy:
            create_params["wordPolicyConfig"] = word_policy
        
        # Call guardrail creation API
        response = bedrock_client.create_guardrail(**create_params)
        
        guardrail_id = response.get('guardrailId', '')
        guardrail_arn = response.get('guardrailArn', '')
        
        print(f"Guardrail created for {role_name}: {guardrail_id}")
        
        # Wait for guardrail to be created and activated
        print(f"Waiting for guardrail to become active...")
        time.sleep(5)  # Minimum wait time
        
        try:
            max_wait_time = 60  # Wait maximum 60 seconds
            start_time = time.time()
            while time.time() - start_time < max_wait_time:
                status_response = bedrock_client.get_guardrail(
                    guardrailIdentifier=guardrail_id
                )
                status = status_response.get('status')
                print(f"Current status: {status}")
    
                # Proceed if status is ACTIVE or READY
                if status in ['ACTIVE', 'READY']:
                    print(f"Guardrail is now {status} and ready to use.")
                    break
        
                time.sleep(5)  # Check status every 5 seconds

            # If maximum wait time is exceeded
            if time.time() - start_time >= max_wait_time:
                print("Warning: Maximum wait time exceeded. Proceeding with current status.")
        except Exception as status_error:
            print(f"Error checking guardrail status: {str(status_error)}")
            # Return ID even if status check fails
        
        return guardrail_id
    
    except Exception as e:
        print(f"Error creating guardrail: {str(e)}")
        # Print detailed information when API call fails
        print("\nRequest parameters:")
        print(json.dumps(create_params, indent=2))
        raise e


# Get list of available roles
def get_available_roles(config_file="guardrail_config.json"):
    """
    Gets the list of available roles from the configuration file.
    
    :param config_file: Configuration file path
    :return: List of role names
    """
    config = load_guardrail_config(config_file)
    if not config:
        return []
    
    return list(config.keys())


# Function to ask Y/N question to user and repeat until clear response is received
def ask_yes_no_question(question, default_hint=True):
    """
    Asks user a yes/no question and repeats until a clear response is received.
    
    :param question: Question to ask
    :param default_hint: Default value direction to show as hint (for UI display)
    :return: User's response (True: yes, False: no)
    """
    prompt = f"{question} {'(Y/n)' if default_hint else '(y/N)'}: "
    while True:
        response = input(prompt).strip().lower()
        
        # Request input again if empty response
        if not response:
            print("A response is required. Please enter 'y' or 'n'.")
            continue
        
        # Clear response
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        
        # Invalid response
        print("Invalid response. Please enter 'y' or 'n'.")


# Check if string contains English characters only
def is_english_only(text):
    """
    Checks if the string consists only of English letters, numbers, spaces, and special characters 
    ('-', '_', '!', '?', '.', ' ').
    
    :param text: String to check
    :return: True if string contains only English characters, etc., False otherwise
    """
    import re
    return bool(re.match(r'^[a-zA-Z0-9\s\-_!?\.]+$', text))


# Main function modified
def main():
    """
    Main function - Create and manage guardrails
    """
    while True:
        print("\nAmazon Bedrock Guardrails Management Tool")
        print("=" * 40)
        print("1. Create Single Guardrail")
        print("2. View Guardrail List")
        print("3. Delete Guardrail")
        print("4. View Available Roles")
        print("5. Exit")
        
        choice = input("\nSelect an operation [1-5]: ")
        
        if choice == '1':
            # Create single guardrail
            print("\n=== Create Guardrail ===")
            
            # Get list of available roles
            available_roles = get_available_roles()
            
            if not available_roles:
                print("Warning: No roles found in configuration file.")
                print("Enter a custom role name.")
            else:
                print(f"Available roles: {', '.join(available_roles)}")
            
            role_name = input("Enter role to apply to guardrail: ")
            
            # Check if role is in configuration file
            if available_roles and role_name not in available_roles:
                print(f"Warning: '{role_name}' is not a defined role in the configuration file. Using default settings.")
            
            user_id = input("Enter user ID: ")
            
            # Check default settings - Use Y/N question function
            check_harmful = ask_yes_no_question("Do you want to enable harmful content filter?", True)
            check_prompt_attacks = ask_yes_no_question("Do you want to enable prompt attack prevention?", True)
            
            # Check if additional topics should be added - Use Y/N question function
            add_topics = ask_yes_no_question("Do you want to add topics to block?", False)
            custom_topics = []
            
            if add_topics:
                print("Enter topics to block. Press Enter on an empty line to finish.")
                print("Format: topic_name,topic description (topic name must be in English/numbers/special chars only)")
                
                while True:
                    topic_input = input("Topic (name|description): ")
                    if not topic_input:
                        break
                    
                    # Split topic name and description
                    parts = topic_input.split('|', 1)
                    topic_name = parts[0].strip()
                    
                    # Check if topic name is in English
                    if not is_english_only(topic_name):
                        print("Error: Topic name must only contain English letters, numbers, and special characters ('-', '_', '!', '?', '.').")
                        print("Please try again.")
                        continue
                    
                    topic_def = parts[1].strip() if len(parts)>1 else f"Topics related to {topic_name}"
                    
                    custom_topics.append({
                        'name': topic_name,
                        'definition': topic_def
                    })
                    
                    print(f"Topic '{topic_name}' has been added.")
            
            # Create guardrail
            guardrail_id = create_dynamic_guardrail(
                role_name, 
                user_id,
                check_harmful_content=check_harmful,
                check_prompt_attacks=check_prompt_attacks,
                custom_denied_topics=custom_topics
            )
            
            print(f"\nGuardrail has been successfully created. ID: {guardrail_id}")
            input("\nPress Enter to continue...")
            
        elif choice == '2':
            # View guardrail list
            bedrock_client = boto3.client('bedrock', region_name=AWS_REGION)
            try:
                response = bedrock_client.list_guardrails()
                guardrails = response.get('guardrails', [])
                
                if not guardrails:
                    print("\nNo guardrails found.")
                else:
                    print(f"\nFound {len(guardrails)} guardrails:")
                    for i, guardrail in enumerate(guardrails):
                        print(f"{i+1}. ID: {guardrail.get('id')}, Name: {guardrail.get('name')}, Status: {guardrail.get('status')}")
            except Exception as e:
                print(f"Error fetching guardrails: {str(e)}")
            
            input("\nPress Enter to continue...")
                
        elif choice == '3':
            # Delete guardrail
            guardrail_id = input("Enter ID of guardrail to delete: ")
            if not guardrail_id:
                print("No guardrail ID entered.")
            else:
                bedrock_client = boto3.client('bedrock', region_name=AWS_REGION)
                try:
                    bedrock_client.delete_guardrail(guardrailIdentifier=guardrail_id)
                    print(f"Guardrail {guardrail_id} has been deleted.")
                except Exception as e:
                    print(f"Error deleting guardrail: {str(e)}")
            
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            # View available roles list
            available_roles = get_available_roles()
            
            if not available_roles:
                print("\nNo roles found in configuration file.")
            else:
                print("\nAvailable roles:")
                for i, role in enumerate(available_roles):
                    print(f"{i+1}. {role}")
                
                # View detailed settings for a specific role
                show_details = input("\nDo you want to see detailed settings for a specific role? (y/N): ").lower() == 'y'
                
                if show_details:
                    role_name = input("Enter the role name to view details: ")
                    config = load_guardrail_config()
                    
                    if role_name in config:
                        role_config = config[role_name]
                        print(f"\n==== Settings for {role_name} role ====")
                        print(json.dumps(role_config, indent=2, ensure_ascii=False))
                    else:
                        print(f"Role '{role_name}' not found.")
            
            input("\nPress Enter to continue...")
        
        elif choice == '5':
            print("Exiting program.")
            break
        
        else:
            print("Invalid selection.")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram terminated.")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
        import traceback
        traceback.print_exc()