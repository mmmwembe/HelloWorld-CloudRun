// static/react/js/components/Sidebar.js

const Sidebar = ({ polygons, selectedIndex, onSelectSegment, getDiatomLabel }) => {
    return (
        <div className="w-96 bg-gray-800 fixed right-0 h-full overflow-y-auto">
            <div className="text-2xl font-bold text-white text-center py-5 border-b border-gray-700">
                Polygons ({polygons.length})
            </div>
            
            <div className="p-4 text-white">
                <p>Instructions:</p>
                <ul className="list-disc pl-5 space-y-2 mt-2">
                    <li>Click to start drawing a polygon</li>
                    <li>Click to add points to the polygon</li>
                    <li>Click near the start point to close the polygon</li>
                    <li>Press ESC to cancel current polygon</li>
                    <li>Click on a segmentation in the list to highlight it</li>
                </ul>
            </div>
            
            <SegmentationList 
                polygons={polygons}
                selectedIndex={selectedIndex}
                onSelectSegment={onSelectSegment}
                getDiatomLabel={getDiatomLabel}
            />
        </div>
    );
};

export default Sidebar;