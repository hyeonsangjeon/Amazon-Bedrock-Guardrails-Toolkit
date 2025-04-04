import boto3
import json
import time
import os

# AWS 리전 설정
AWS_REGION = "us-east-1"  # 사용하려는 리전으로 변경 (예: us-east-1, ap-northeast-2 등)

# 구성 파일 로드
def load_guardrail_config(config_file="guardrail_config.json"):
    """
    가드레일 구성 파일을 로드합니다.
    
    :param config_file: 구성 파일 경로
    :return: 구성 딕셔너리
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"가드레일 구성 파일 '{config_file}'을 성공적으로 로드했습니다.")
        return config
    except FileNotFoundError:
        print(f"오류: 구성 파일 '{config_file}'을 찾을 수 없습니다.")
        return {}
    except json.JSONDecodeError:
        print(f"오류: 구성 파일 '{config_file}'의 JSON 형식이 올바르지 않습니다.")
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
    구성 파일의 역할 설정에 기반하여 가드레일을 동적으로 생성
    
    :param role_name: 구성 파일에 정의된 역할 이름
    :param user_id: 사용자 식별자
    :param check_harmful_content: 유해 콘텐츠 필터 활성화 여부
    :param check_prompt_attacks: 프롬프트 공격 방지 활성화 여부
    :param custom_denied_topics: 추가 거부 주제 목록 (기본 설정에 추가됨)
    :param config_file: 가드레일 구성 파일 경로
    :param region: AWS 리전
    :return: 생성된 가드레일 ID
    """
    # 베드락 클라이언트 생성
    bedrock_client = boto3.client('bedrock', region_name=region)
    
    # 구성 파일 로드
    config = load_guardrail_config(config_file)
    
    # 기본 설정 초기화
    content_filter_level = "MEDIUM"
    blocked_topics = []
    block_message = f"{role_name} 권한으로는 답변이 제한됩니다."
    blocked_input_message = f"{role_name} 권한으로는 이러한 입력이 허용되지 않습니다."
    enable_profanity_filter = True
    custom_denied_words = []
    
    # 역할 이름에 해당하는 구성이 있으면 로드
    if config and role_name in config:
        role_config = config[role_name]
        content_filter_level = role_config.get('content_filter_level', content_filter_level)
        blocked_topics = role_config.get('blocked_topics', blocked_topics)
        block_message = role_config.get('block_message', block_message)
        blocked_input_message = role_config.get('blocked_input_message', blocked_input_message)
        enable_profanity_filter = role_config.get('enable_profanity_filter', enable_profanity_filter)
        custom_denied_words = role_config.get('denied_words', custom_denied_words)
        
        print(f"'{role_name}' 역할 설정을 구성 파일에서 로드했습니다.")
    else:
        print(f"경고: '{role_name}' 역할에 대한 설정을 찾을 수 없습니다. 기본 설정을 사용합니다.")
    
    # 추가 거부 주제 처리
    if custom_denied_topics:
        for topic in custom_denied_topics:
            if isinstance(topic, dict) and 'name' in topic and 'definition' in topic:
                # 이미 존재하는 주제인지 확인
                existing = False
                for existing_topic in blocked_topics:
                    if isinstance(existing_topic, dict) and existing_topic.get('name') == topic['name']:
                        existing = True
                        break
                
                if not existing:
                    blocked_topics.append(topic)
    
    # 필터 상태 로그
    print(f"\n=== Configuration for {role_name} ===")
    print(f"- Content filter level: {content_filter_level}")
    print(f"- Harmful content filter: {'Enabled' if check_harmful_content else 'Disabled'}")
    print(f"- Prompt attack prevention: {'Enabled' if check_prompt_attacks else 'Disabled'}")
    print(f"- Profanity filter: {'Enabled' if enable_profanity_filter else 'Disabled'}")
    
    # 주제 정책 로그
    if blocked_topics:
        print(f"- Blocked topics: {len(blocked_topics)}")
        for topic in blocked_topics:
            name = topic['name'] if isinstance(topic, dict) else topic
            definition = topic.get('definition', 'No definition') if isinstance(topic, dict) else f"Topics related to {topic}"
            print(f"  • {name}: {definition}")
    else:
        print("- No blocked topics")
    
    # 사용자 지정 단어 로그
    if custom_denied_words:
        print(f"- Denied words: {len(custom_denied_words)}")
        for word in custom_denied_words:
            masked_word = word[0] + '*' * (len(word) - 2) + word[-1] if len(word) > 2 else word
            print(f"  • {masked_word}")
    else:
        print("- No denied words")
    
    # 주제 정책 구성 - 주제 형식 통일
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
    
    # 콘텐츠 정책 필터 구성
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
    
    # 프롬프트 공격 방지 설정
    if check_prompt_attacks:
        filters_config.append({
            "type": "PROMPT_ATTACK",
            "inputStrength": content_filter_level,
            "outputStrength": "NONE"  # 출력에는 프롬프트 공격 필터를 적용하지 않음
        })
    
    # 단어 정책 구성
    words_config = []
    for word in custom_denied_words:
        words_config.append({
            "text": word
        })
    
    # 관리형 단어 목록 구성
    managed_word_lists_config = []
    if enable_profanity_filter:
        managed_word_lists_config.append({
            "type": "PROFANITY"
        })
    
    # 태그 형식 변경 (딕셔너리 → 리스트로 변환)
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
    
    # 가드레일 생성 (새로운 API 구조에 맞게 변경)
    try:
        create_params = {
            "name": f"Guardrail-{role_name}-{user_id}",
            "description": f"Dynamically generated guardrail for {role_name}",
            "blockedInputMessaging": blocked_input_message,
            "blockedOutputsMessaging": block_message,
            "tags": tags_list,
            "clientRequestToken": f"{role_name}-{user_id}-{int(time.time())}"
        }
        
        # 주제 정책이 있는 경우에만 추가
        if topics_config:
            create_params["topicPolicyConfig"] = {
                "topicsConfig": topics_config
            }
        
        # 콘텐츠 필터가 있는 경우에만 추가
        if filters_config:
            create_params["contentPolicyConfig"] = {
                "filtersConfig": filters_config
            }
        
        # 단어 정책 구성 추가
        word_policy = {}
        if words_config:
            word_policy["wordsConfig"] = words_config
        
        if managed_word_lists_config:
            word_policy["managedWordListsConfig"] = managed_word_lists_config
        
        if word_policy:
            create_params["wordPolicyConfig"] = word_policy
        
        # 가드레일 생성 API 호출
        response = bedrock_client.create_guardrail(**create_params)
        
        guardrail_id = response.get('guardrailId', '')
        guardrail_arn = response.get('guardrailArn', '')
        
        print(f"Guardrail created for {role_name}: {guardrail_id}")
        
        # 가드레일이 생성되고 활성화될 때까지 대기
        print(f"Waiting for guardrail to become active...")
        time.sleep(5)  # 최소 대기 시간
        
        try:
            max_wait_time = 60  # 최대 60초 대기
            start_time = time.time()
            while time.time() - start_time < max_wait_time:
                status_response = bedrock_client.get_guardrail(
                    guardrailIdentifier=guardrail_id
                )
                status = status_response.get('status')
                print(f"Current status: {status}")
    
                # ACTIVE 또는 READY 상태면 진행
                if status in ['ACTIVE', 'READY']:
                    print(f"Guardrail is now {status} and ready to use.")
                    break
        
                time.sleep(5)  # 5초마다 상태 확인

            # 최대 대기 시간을 초과했을 경우
            if time.time() - start_time >= max_wait_time:
                print("Warning: Maximum wait time exceeded. Proceeding with current status.")
        except Exception as status_error:
            print(f"Error checking guardrail status: {str(status_error)}")
            # 상태 확인에 실패해도 ID는 반환
        
        return guardrail_id
    
    except Exception as e:
        print(f"Error creating guardrail: {str(e)}")
        # API 호출 오류 시 자세한 정보 출력
        print("\nRequest parameters:")
        print(json.dumps(create_params, indent=2))
        raise e


# 사용 가능한 역할 목록 가져오기
def get_available_roles(config_file="guardrail_config.json"):
    """
    구성 파일에서 사용 가능한 역할 목록을 가져옵니다.
    
    :param config_file: 구성 파일 경로
    :return: 역할 이름 목록
    """
    config = load_guardrail_config(config_file)
    if not config:
        return []
    
    return list(config.keys())


# 사용자에게 Y/N 질문을 하고 명확한 응답을 받을 때까지 반복하는 함수
def ask_yes_no_question(question, default_hint=True):
    """
    사용자에게 예/아니오 질문을 하고 명확한 응답을 받을 때까지 반복합니다.
    
    :param question: 물어볼 질문
    :param default_hint: 힌트로 표시할 기본값 방향(UI 표시용)
    :return: 사용자의 응답 (True: 예, False: 아니오)
    """
    prompt = f"{question} {'(Y/n)' if default_hint else '(y/N)'}: "
    while True:
        response = input(prompt).strip().lower()
        
        # 빈 응답일 경우 다시 입력 요청
        if not response:
            print("응답이 필요합니다. 'y' 또는 'n'을 입력해주세요.")
            continue
        
        # 명확한 응답일 경우
        if response in ['y', 'yes', '예', '네']:
            return True
        elif response in ['n', 'no', '아니오', '아니요']:
            return False
        
        # 유효하지 않은 응답
        print("유효한 응답이 아닙니다. 'y' 또는 'n'을 입력해주세요.")


# 영문 문자열 확인 함수
def is_english_only(text):
    """
    문자열이 영문자, 숫자, 공백, 특수문자('-', '_', '!', '?', '.', ' ')로만 구성되어 있는지 확인합니다.
    
    :param text: 확인할 문자열
    :return: 영문자 등으로만 구성되어 있으면 True, 그렇지 않으면 False
    """
    import re
    return bool(re.match(r'^[a-zA-Z0-9\s\-_!?\.]+$', text))


# 메인 함수 수정
def main():
    """
    메인 함수 - 가드레일 생성 및 관리
    """
    while True:
        print("\nAmazon Bedrock Guardrails 관리 도구")
        print("=" * 40)
        print("1. 단일 가드레일 생성")
        print("2. 가드레일 목록 조회")
        print("3. 가드레일 삭제")
        print("4. 사용 가능한 역할 목록 보기")
        print("5. 종료")
        
        choice = input("\n작업을 선택하세요 [1-5]: ")
        
        if choice == '1':
            # 단일 가드레일 생성
            print("\n=== 가드레일 생성 ===")
            
            # 사용 가능한 역할 목록 가져오기
            available_roles = get_available_roles()
            
            if not available_roles:
                print("경고: 구성 파일에서 역할을 찾을 수 없습니다.")
                print("커스텀 역할 이름을 입력하세요.")
            else:
                print(f"사용 가능한 역할: {', '.join(available_roles)}")
            
            role_name = input("가드레일에 적용할 역할을 입력하세요: ")
            
            # 역할이 구성 파일에 있는지 확인
            if available_roles and role_name not in available_roles:
                print(f"경고: '{role_name}'은(는) 구성 파일에 정의된 역할이 아닙니다. 기본 설정을 사용합니다.")
            
            user_id = input("사용자 ID를 입력하세요: ")
            
            # 기본 설정 확인 - Y/N 질문 함수 사용
            check_harmful = ask_yes_no_question("유해 콘텐츠 필터를 활성화하시겠습니까?", True)
            check_prompt_attacks = ask_yes_no_question("프롬프트 공격 방지를 활성화하시겠습니까?", True)
            
            # 추가 주제 지정 여부 - Y/N 질문 함수 사용
            add_topics = ask_yes_no_question("차단할 주제를 추가하시겠습니까?", False)
            custom_topics = []
            
            if add_topics:
                print("차단할 주제를 입력하세요. 입력을 마치려면 빈 줄을 입력하세요.")
                print("형식: 주제명,주제 설명 (주제명은 영문/숫자/특수문자만 가능)")
                
                while True:
                    topic_input = input("주제 (주제명,설명): ")
                    if not topic_input:
                        break
                    
                    # 주제명과 설명 분리
                    parts = topic_input.split(',', 1)
                    topic_name = parts[0].strip()
                    
                    # 주제명이 영문인지 확인
                    if not is_english_only(topic_name):
                        print("오류: 주제명은 영문자, 숫자, 특수문자('-', '_', '!', '?', '.')만 사용 가능합니다.")
                        print("다시 입력해주세요.")
                        continue
                    
                    topic_def = parts[1].strip() if len(parts) > 1 else f"Topics related to {topic_name}"
                    
                    custom_topics.append({
                        'name': topic_name,
                        'definition': topic_def
                    })
                    
                    print(f"주제 '{topic_name}'이(가) 추가되었습니다.")
            
            # 가드레일 생성
            guardrail_id = create_dynamic_guardrail(
                role_name, 
                user_id,
                check_harmful_content=check_harmful,
                check_prompt_attacks=check_prompt_attacks,
                custom_denied_topics=custom_topics
            )
            
            print(f"\n가드레일이 성공적으로 생성되었습니다. ID: {guardrail_id}")
            input("\n계속하려면 Enter 키를 누르세요...")
            
        elif choice == '2':
            # 가드레일 목록 조회
            bedrock_client = boto3.client('bedrock', region_name=AWS_REGION)
            try:
                response = bedrock_client.list_guardrails()
                guardrails = response.get('guardrails', [])
                
                if not guardrails:
                    print("\n가드레일이 없습니다.")
                else:
                    print(f"\n총 {len(guardrails)}개의 가드레일이 있습니다:")
                    for i, guardrail in enumerate(guardrails):
                        print(f"{i+1}. ID: {guardrail.get('id')}, 이름: {guardrail.get('name')}, 상태: {guardrail.get('status')}")
            except Exception as e:
                print(f"가드레일 목록 조회 중 오류 발생: {str(e)}")
            
            input("\n계속하려면 Enter 키를 누르세요...")
                
        elif choice == '3':
            # 가드레일 삭제
            guardrail_id = input("삭제할 가드레일 ID를 입력하세요: ")
            if not guardrail_id:
                print("가드레일 ID가 입력되지 않았습니다.")
            else:
                bedrock_client = boto3.client('bedrock', region_name=AWS_REGION)
                try:
                    bedrock_client.delete_guardrail(guardrailIdentifier=guardrail_id)
                    print(f"가드레일 {guardrail_id}이(가) 삭제되었습니다.")
                except Exception as e:
                    print(f"가드레일 삭제 중 오류 발생: {str(e)}")
            
            input("\n계속하려면 Enter 키를 누르세요...")
        
        elif choice == '4':
            # 사용 가능한 역할 목록 조회
            available_roles = get_available_roles()
            
            if not available_roles:
                print("\n구성 파일에서 역할을 찾을 수 없습니다.")
            else:
                print("\n사용 가능한 역할 목록:")
                for i, role in enumerate(available_roles):
                    print(f"{i+1}. {role}")
                
                # 특정 역할의 상세 설정 보기
                show_details = input("\n특정 역할의 상세 설정을 보시겠습니까? (y/N): ").lower() == 'y'
                
                if show_details:
                    role_name = input("상세 정보를 볼 역할 이름을 입력하세요: ")
                    config = load_guardrail_config()
                    
                    if role_name in config:
                        role_config = config[role_name]
                        print(f"\n==== {role_name} 역할 설정 ====")
                        print(json.dumps(role_config, indent=2, ensure_ascii=False))
                    else:
                        print(f"'{role_name}' 역할을 찾을 수 없습니다.")
            
            input("\n계속하려면 Enter 키를 누르세요...")
        
        elif choice == '5':
            print("프로그램을 종료합니다.")
            break
        
        else:
            print("잘못된 선택입니다.")
            input("\n계속하려면 Enter 키를 누르세요...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n프로그램이 강제 종료되었습니다.")
    except Exception as e:
        print(f"\n오류가 발생했습니다: {str(e)}")
        import traceback
        traceback.print_exc()