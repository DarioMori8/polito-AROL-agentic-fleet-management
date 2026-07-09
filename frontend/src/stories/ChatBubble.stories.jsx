import React from 'react';
import ChatBubble from '../components/chat/ChatBubble';
import '../styles/index.css';
import '../styles/ChatBubble.css';

export default {
    title: 'UI/ChatBubble',
    component: ChatBubble,
};

const Template = (args) => <ChatBubble {...args} />;

// Scenario 1: Assistant message with citations (RAG) and high confidence
export const AssistantResponse = Template.bind({});
AssistantResponse.args = {
    message: {
        sender: 'assistant',
        text: 'To resolve the abnormal vibration on the Capper #12 belt, follow this procedure:\n- Stop the machine by pressing the red emergency mushroom button.\n- Check the alignment of the idler rollers on the lower rail.\n- Check the tightening torque of the base bolts.',
        timestamp: '14:20',
        citations: [
            { docName: 'Capper_12_Manual_EN.pdf', page: 45 },
            { docName: 'Tightening_Specs_Q2.pdf', page: 12 }
        ],
        metadata: { confidence: 0.94 }
    }
};

// Scenario 2: Connection error during maintainer's message send
export const UserConnectionError = Template.bind({});
UserConnectionError.args = {
    message: {
        sender: 'user',
        text: 'The current tightening torque is 15Nm, shall I proceed?',
        timestamp: '14:21',
        status: 'error'
    },
    onRetry: (msg) => alert(`Retry attempt for: "${msg.text}"`)
};