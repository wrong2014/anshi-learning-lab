// ===== API 响应类型 =====

export interface UIBlock {
  type: string; // 'single_choice' | 'multi_choice' | 'short_text'
  id: string;
  title?: string;
  body?: string;
  options?: { id: string; label: string }[];
  allow_skip?: boolean;
  allow_free_text?: boolean;
  free_text_label?: string;
  free_text_placeholder?: string;
  min_select?: number;
  max_select?: number;
}

export interface AgentMessageData {
  text: string;
  ui_block?: UIBlock | null;
}

export interface ResultData {
  subject?: string;
  subject_label?: string;
  grade_label?: string;
  confidence?: 'low' | 'medium' | 'high' | string;
  primary_category?: string;
  primary_category_label?: string;
  primary_factor?: string;
  primary_desc?: string;
  secondary_factors?: string[];
  amplifier?: string | null;
  amplifier_label?: string | null;
  evidence?: string[];
  uncertainties?: string[];
  missing_information?: string[];
  verification_action?: {
    title?: string;
    steps?: string;
    observe?: string;
  };
  parent_common_mistake?: string;
  next_7_days_stop?: string;
  next_7_days_start?: string;
  public_summary?: string;
  diagnostic_upgrade?: string;
}

export interface APIStartResponse {
  session_id: string;
  active_ui_block_id?: string | null;
  agent_messages: AgentMessageData[];
  is_complete: boolean;
  result?: ResultData | null;
}

export interface APIAnswerRequest {
  session_id: string;
  ui_block_id?: string;
  free_text?: string;
  selected_option_ids?: string[];
  selected_labels?: string[];
}

export interface APIAnswerResponse {
  session_id: string;
  active_ui_block_id?: string | null;
  agent_messages: AgentMessageData[];
  is_complete: boolean;
  result?: ResultData | null;
}

// ===== 前端 UI 消息类型 =====

export interface Message {
  id: string;
  role: 'user' | 'agent';
  content: string;
  uiBlock?: UIBlock | null;
  result?: ResultData | null;
}

export interface StoredSessionSummary {
  session_id: string;
  title: string;
  preview: string;
  turn_count: number;
  is_complete: boolean;
  created_at: string;
  updated_at: string;
}

export interface StoredMessage {
  role: 'user' | 'agent';
  content: string;
  uiBlock?: UIBlock | null;
  result?: ResultData | null;
}

export interface StoredSessionDetail extends StoredSessionSummary {
  messages: StoredMessage[];
}

export interface ProviderStatus {
  enable_llm: boolean;
  default_text_provider: string;
  deepseek_ready: boolean;
  doubao_ready: boolean;
  deepseek_model?: string | null;
  doubao_text_model?: string | null;
  mode: string;
}
