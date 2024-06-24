import os
import json
from dotenv import load_dotenv

class config:

    def __init__(self, config_file: str = None):

        load_dotenv()  
        
        self.config_file = os.path.expanduser(config_file) if config_file else os.getenv('CONFIG_FILE')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.serp_api_key = os.getenv("SERP_API_KEY")
        self.mongodb_url = f"mongodb://mongo:{os.getenv('MONGODB_PORT')}"
        self.tg_token = os.getenv("TELEGRAM_TOKEN")
        self.OPENAI_CONFIG = {
            'temperature': float(os.getenv('TEMPERATURE', 0.55)),
            'top_p': int(os.getenv('TOP_P', 1)),
            'frequency_penalty': int(os.getenv('FREQUENCY_PENALTY', 0)),
            'presence_penalty': int(os.getenv('PRESENCE_PENALTY', 0)),
            'request_timeout': float(os.getenv('REQUEST_TIMEOUT', 60.0))
        }
        self.n_rate_per_page = int(os.getenv("N_RATE_PER_PAGE", 5))
        self.new_dialog_timeout = int(os.getenv("NEW_DIALOG_TIMEOUT", 3600))
        self.proxies = os.getenv("PROXIES", "").split()
        self.tts_model = os.getenv("TTS_MODEL", "tts-1")
        self.tts_voice = os.getenv("TTS_VOICE", "cove")
        self.whisper_prompt = os.getenv("WHISPER_PROMPT", "")
        self.available_text_models = os.getenv("AVAILABLE_TEXT_MODELS", "gpt-4o").split()
        self.available_free_text_models = os.getenv("AVAILABLE_TEXT_MODELS", "gpt-4o").split()
        self.prompt_start = os.getenv("PROMPT_START", "")
        self.assistant_id = os.getenv("ASSISTANT_ID")
        self.assistant_partner_id = os.getenv("ASSISTANT_PARTNER_ID")
        self.support_url = os.getenv("SUPPORT_URL")
        self.diseases_url = os.getenv("DISEASES_URL")
        self.partner_extend_prompt = "\nОтвечай только при помощи информации \
                                     данной тебе в файлах, применяй данные \
                                     оттуда только если они на 100% подходят клиенту"
        self.db_name = os.getenv("DB_NAME")
        self.base_plot_path = os.getenv("BASE_PLOT_PATH")
        self.shop_token = os.getenv("SHOP_TOKEN")
        self.sec_key = os.getenv("SEC_KEY")
        self.service_code = os.getenv("SERVICE_CODE")
        self.main_bot_url = os.getenv("BOT_URL")
        self.offer_doc_path = os.getenv("OFFER_DOC_PATH")
        self.notification_url = os.getenv("NOTIFICATION_URL")
        self.TOKEN_COST = float(os.getenv("TOKEN_COST", 0.000015))
        self.TRANSCRIBE_SECOND_COST = float(os.getenv("TRANSCRIBE_SECOND_COST", 0.0001))
        self.GENERATE_SECOND_COST = float(os.getenv("GENERATE_SECOND_COST", 0.000015))
        self.admins_ids = list(map(int, os.getenv("ADMINS_IDS", "5484401110").split(',')))
    # def validate_doc_path(self):
    #     os.makedirs(self.doc_path, exist_ok=True)

    def load_config_file(self) -> None:
        if self.config_file is None:
            return None
        with open(self.config_file, "r") as f:
            config_ = json.load(f)
        for key, value in config_.items():
            setattr(self, key.lower(), value)


Config = config()
Config.load_config_file()
