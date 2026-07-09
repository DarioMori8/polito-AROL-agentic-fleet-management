import React from 'react';
import Button from '../components/ui/Button';
import '../styles/index.css';
import '../styles/Button.css';

export default {
  title: 'UI/Button',
  component: Button,
  // Gli "argTypes" definiscono come mappare le props ai controlli grafici di Storybook
  argTypes: {
    variant: {
      name: 'Variante (variant)',
      control: { type: 'select' }, // Genera un menu a discesa (dropdown)
      options: ['primary', 'secondary', 'danger', 'success', 'outline'],
      description: 'Stile estetico ad alto contrasto per ambiente industriale (WCAG)',
      table: {
        defaultValue: { summary: 'primary' },
      },
    },
    disabled: {
      name: 'Disabilitato (disabled)',
      control: { type: 'boolean' }, // Genera un interruttore ON/OFF (toggle)
      description: "Disabilita l'interazione (es. perdita segnale Wi-Fi o caricamento)",
      table: {
        defaultValue: { summary: 'false' },
      },
    },
    className: {
      name: 'Classi CSS extra (className)',
      control: { type: 'text' }, // Genera un campo di testo libero
      description: 'Classi CSS addizionali per gestire margini e layout nel flusso di chat',
    },
    onClick: {
      action: 'clicked',
      description: 'Evento di click registrato'
    },
  },
};

// Configurazione della Storia Base (Template)
const Template = (args) => <Button {...args}>{args.children || 'Avvia'}</Button>;

export const Default = Template.bind({});
Default.args = {
  variant: 'primary',
  disabled: false,
  className: '',
  children: 'Invia Comando', // Prop speciale per il testo del pulsante
};