// static/react/js/components/DiatomSelector.js

const DiatomSelector = ({ selected, setSelected }) => {
    const options = [
        { label: 'Incomplete Diatom', value: 0 },
        { label: 'Complete Diatom', value: 1 },
        { label: 'Fragment Diatom', value: 2 },
        { label: 'Blurred Diatom', value: 3 },
        { label: 'Diatom SideView', value: 4 }
    ];

    return (
        <div className="p-4">
            <div className="flex flex-wrap gap-6 items-center justify-center">
                {options.map((option) => (
                    <label key={option.value} className="flex items-center space-x-2 cursor-pointer">
                        <input
                            type="radio"
                            name="diatom-type"
                            value={option.value}
                            checked={selected === option.value}
                            onChange={(e) => setSelected(Number(e.target.value))}
                            className="w-4 h-4 text-blue-600 cursor-pointer"
                        />
                        <span className="text-sm font-medium text-gray-700">
                            {option.label}
                        </span>
                    </label>
                ))}
            </div>
        </div>
    );
};