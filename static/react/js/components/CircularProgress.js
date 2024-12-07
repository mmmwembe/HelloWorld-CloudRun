// static/react/js/components/CircularProgress.js

const CircularProgress = ({ progress }) => {
    const radius = 20;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (progress / 100) * circumference;
    
    return (
        <svg className="transform -rotate-90 w-12 h-12">
            <circle
                className="text-gray-300"
                strokeWidth="4"
                stroke="currentColor"
                fill="transparent"
                r={radius}
                cx="24"
                cy="24"
            />
            <circle
                className="text-green-500"
                strokeWidth="4"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                stroke="currentColor"
                fill="transparent"
                r={radius}
                cx="24"
                cy="24"
            />
            <text
                x="24"
                y="24"
                className="text-xs font-medium"
                fill="currentColor"
                textAnchor="middle"
                alignmentBaseline="middle"
                transform="rotate(90 24 24)"
            >
                {Math.round(progress)}%
            </text>
        </svg>
    );
};

export default CircularProgress;