export type UIBlock = {
  type: 'single_choice' | 'multi_choice' | 'scale' | 'result_card';
  id: string;
  options?: { id: string; label: string }[];
  title?: string;
  data?: any; // For result card
};

export type Message = {
  id: string;
  role: 'user' | 'agent';
  content: string;
  uiBlock?: UIBlock;
};

export const initialMockMessages: Message[] = [
  {
    id: '1',
    role: 'agent',
    content: '你好，我是理科学习卡点定位助手。我不会急着给孩子下诊断，而是希望通过你们最近遇到的一次真实困难，一起来发现可能的原因。请问孩子最近一次在学习数学、物理或化学时卡住，具体是怎样的场景呢？'
  }
];
