// static/react/js/components/SegmentationList.js

const SegmentationList = ({ polygons, selectedIndex, onSelectSegment, getDiatomLabel }) => {
    return (
        <div className="mt-4 space-y-2 px-4">
            {polygons.map((polygon, index) => (
                <div
                    key={index}
                    onClick={() => onSelectSegment(index)}
                    className={`p-3 rounded-lg cursor-pointer transition-all duration-200 ${
                        selectedIndex === index 
                            ? 'bg-blue-600 text-white shadow-lg transform scale-105' 
                            : 'bg-gray-700 text-gray-200 hover:bg-gray-600'
                    }`}
                >
                    <div className="flex items-center justify-between">
                        <span className="font-medium">
                            {index + 1}. {getDiatomLabel(polygon.label)}
                        </span>
                        <div 
                            className="w-4 h-4 rounded-full" 
                            style={{ backgroundColor: polygon.color }}
                        />
                    </div>
                    
                    {selectedIndex === index && (
                        <div className="mt-2 text-sm opacity-80">
                            <div>Points: {polygon.points.length}</div>
                            {polygon.denorm_bbox && (
                                <div>Bbox: {polygon.denorm_bbox}</div>
                            )}
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
};