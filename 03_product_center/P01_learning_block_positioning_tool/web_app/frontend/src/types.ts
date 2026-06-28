// ===== API 响应类型 =====

export interface UIBlockOption {
  id: string;
  label: string;
  hint?: string;
}

export interface UIBlock {
  type: string; // 'single_choice' | 'multi_choice' | 'subject_picker'
  id: string;
  title?: string;
  body?: string;
  options?: UIBlockOption[];
}

export interface VerificationAction {
  title: string;
  steps: string;
  observe: string;
}

export interface ResultData {
  subject?: string;
  subject_label?: string;
  grade_label?: string;
  confidence?: string;
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
  verification_action?: VerificationAction | null;
  parent_common_mistake?: string;
  next_7_days_stop?: string;
  next_7_days_start?: string;
  public_summary?: string;
  diagnostic_upgrade?: string;
}

export interface AgentMessageData {
  text: string;
  ui_block?: UIBlock | null;
}

export interface APIStartResponse {
  session_id: string;
  agent_messages: AgentMessageData[];
  is_complete: boolean;
  result?: ResultData | null;
}

export interface APIAnswerRequest {
  session_id: string;
  free_text?: string;
  selected_option_ids?: string[];
  selected_labels?: string[];
}

export interface APIAnswerResponse {
  session_id: string;
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
