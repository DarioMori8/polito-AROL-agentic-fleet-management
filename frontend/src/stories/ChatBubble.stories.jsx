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

// Scenario 3: AI response WITH thinking text visible (accordion collapsed by default)
export const AssistantWithThinking = Template.bind({});
AssistantWithThinking.args = {
    message: {
        sender: 'assistant',
        text: 'The tightening torque for the M16 base bolts must be **120.0 Nm** as specified in the anchoring manual.',
        timestamp: '14:22',
        status: 'sent',
        thinkingText: `The user is asking about torque specs for M16 bolts on the capper base.
Let me reason through this: the machine is a Euro VP series, so I need to look at the anchoring specifications document.
The anchoring spec document (Specifiche_Ancoraggio_AROL.pdf) states M16 class 8.8 steel rods, torqued to 120.0 Nm ±5 Nm on cured concrete of min 25 MPa.
I should cite this clearly and make sure the operator knows the tolerance range.`,
        citations: [
            { docName: 'Specifiche_Ancoraggio_AROL.pdf', page: 15 }
        ],
        metadata: { confidence: 0.97 }
    }
};

// Scenario 4: AI still streaming — thinking arrived but response text not yet
export const AssistantThinkingOnly = Template.bind({});
AssistantThinkingOnly.args = {
    message: {
        sender: 'assistant',
        text: '',
        timestamp: '14:23',
        status: 'sending',
        thinkingText: `Analyzing the query about capper vibration...
Checking the Euro VP maintenance manual for roller bearing specs.
Cross-referencing with the vibration alarm thresholds table on page 38.`,
    }
};