// ===== API 响应类型 =====

export interface UIBlock {
  type: string; // 'single_choice' | 'multi_choice' | 'short_text'
  id: string;
  title?: string;
  options?: { id: string; label: string }[];
}

export interface AgentMessageData {
  text: string;
  ui_block?: UIBlock | null;
}

export interface ResultData {
  subject?: string;
  primary_factor?: string;
  primary_desc?: string;
  secondary_factors?: string[];
  evidence?: string[];
  missing_information?: string[];
  parent_common_mistake?: string;
  next_7_days_stop?: string;
  next_7_days_start?: string;
  public_summary?: string;
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
