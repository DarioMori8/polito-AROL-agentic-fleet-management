import React from 'react';
import ChatInput from '../components/chat/ChatInput';
import '../styles/index.css';
import '../styles/ChatInput.css';
import '../styles/Button.css';

export default {
    title: 'UI/ChatInput',
    component: ChatInput,
    argTypes: {
        disabled: {
            name: 'Disabilitato (disabled)',
            control: { type: 'boolean' },
            description: 'Disabilita l’invio e la digitazione (es. durante lo streaming dell’AI)',
        },
        placeholder: {
            name: 'Testo segnaposto',
            control: { type: 'text' },
        }
    }
};

const Template = (args) => (
    <div style={{ backgroundColor: '#F4F5F7', padding: '24px', minHeight: '200px', display: 'flex', alignItems: 'flex-end' }}>
        <ChatInput {...args} />
    </div>
);

export const Default = Template.bind({});
Default.args = {
    disabled: false,
    placeholder: "Type here...",
    onSendMessage: (data) => console.log("Message sent:", data),
    onAttachmentSelect: (file) => console.log("Attachment added:", file)
};