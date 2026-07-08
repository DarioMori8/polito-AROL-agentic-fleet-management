import '../../styles/Button.css';

/**
 * Button optimized for industrial environments (Rugged UI).
 * Minimum touch target guaranteed at 48px for use with protective gloves.
 */
export default function Button({
    children,
    onClick,
    variant = 'primary',
    className = '',
    disabled = false,
    ...props
}) {

    const buttonClassNames = [
        'btn-rugged',
        variant,
        className
    ].filter(Boolean).join(' ');

    return (
        <button
            onClick={onClick}
            disabled={disabled}
            className={buttonClassNames}
            {...props}
        >
            {children}
        </button>
    );
}