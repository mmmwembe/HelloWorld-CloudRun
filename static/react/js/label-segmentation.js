// static/react/js/App.js

const App = () => {
    // State declarations
    const [imageIndex, setImageIndex] = useState(0);
    const [totalImages, setTotalImages] = useState(0);
    const [polygons, setPolygons] = useState([]);
    const [currentPolygon, setCurrentPolygon] = useState([]);
    const [isDrawing, setIsDrawing] = useState(false);
    const [imageUrl, setImageUrl] = useState('');
    const [isSaving, setIsSaving] = useState(false);
    const [isUpdating, setIsUpdating] = useState(false);
    const [saveProgress, setSaveProgress] = useState(0);
    const [showToast, setShowToast] = useState(false);
    const [toastMessage, setToastMessage] = useState('');
    const [selectedType, setSelectedType] = useState(1);
    const [imageData, setImageData] = useState(null);
    const [selectedSegmentIndex, setSelectedSegmentIndex] = useState(null);
    const [error, setError] = useState(null);

    // Refs
    const canvasRef = React.useRef(null);
    const imageRef = React.useRef(null);
    const containerRef = React.useRef(null);

    // Load image data
    useEffect(() => {
        loadImageData(imageIndex);
    }, [imageIndex]);

    const loadImageData = async (index) => {
        try {
            const response = await fetch(`/api/diatoms?index=${index}`);
            const data = await response.json();
            
            if (data.error) {
                setError(data.error);
                return;
            }

            setImageUrl(data.data.image_url);
            setImageData(data.data);
            setTotalImages(data.total_images);
            setImageIndex(data.current_index);
            setSelectedSegmentIndex(null);

            if (data.data.segmentation_url) {
                const segResponse = await fetch(
                    `/api/get_segmentation?url=${encodeURIComponent(data.data.segmentation_url)}&image_index=${index}`
                );
                
                if (!segResponse.ok) {
                    throw new Error('Failed to fetch segmentation data');
                }
                
                const segData = await segResponse.json();
                if (segData.annotations) {
                    const processedPolygons = parseSegmentationText(
                        segData.annotations,
                        data.data.image_width,
                        data.data.image_height
                    );
                    setPolygons(processedPolygons);
                }
            } else {
                setPolygons([]);
            }
        } catch (error) {
            setError('Failed to load image data');
            console.error('Error:', error);
        }
    };

    const handleUpdateSegmentations = async () => {
        setIsUpdating(true);
        setError(null);
        
        try {
            const response = await fetch('/api/update_segmentations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image_index: imageIndex })
            });
            
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || 'Update failed');
            }
            
            setToastMessage(`Successfully updated ${data.updated_count} segmentations`);
            setShowToast(true);
            
            await loadImageData(imageIndex);
            
        } catch (error) {
            setError(error.message || 'Failed to update segmentations');
        } finally {
            setIsUpdating(false);
        }
    };

    const handleCanvasClick = async (e) => {
        const rect = canvasRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        if (!isDrawing) {
            setIsDrawing(true);
            setCurrentPolygon([{ x, y }]);
        } else {
            const startPoint = currentPolygon[0];
            const distance = Math.sqrt(
                Math.pow(x - startPoint.x, 2) + Math.pow(y - startPoint.y, 2)
            );

            if (distance < 20 && currentPolygon.length > 2) {
                const newPolygon = {
                    label: selectedType,
                    points: currentPolygon,
                    color: getRandomColor()
                };
                
                const updatedPolygons = [...polygons, newPolygon];
                setPolygons(updatedPolygons);
                setCurrentPolygon([]);
                setIsDrawing(false);
                
                await handleSave(updatedPolygons);
            } else {
                setCurrentPolygon([...currentPolygon, { x, y }]);
            }
        }
    };

    const handleSave = async (polygonsToSave = polygons) => {
        setIsSaving(true);
        setSaveProgress(0);
        setError(null);
        
        const progressInterval = setInterval(() => {
            setSaveProgress(prev => Math.min(prev + 10, 90));
        }, 100);

        try {
            const imageFileName = imageUrl.split('/').pop().replace(/\.[^/.]+$/, '');
            
            // Calculate enhanced data for each polygon
            const enhancedPolygons = polygonsToSave.map(polygon => {
                const enhancedData = calculatePolygonData(
                    polygon.points,
                    imageData.image_width,
                    imageData.image_height
                );
                
                return {
                    ...polygon,
                    ...enhancedData
                };
            });

            const response = await fetch('/api/save_segmentation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_index: imageIndex,
                    segmentation_data: generateSegmentationText(
                        enhancedPolygons,
                        imageData.image_width,
                        imageData.image_height
                    ),
                    image_filename: imageFileName,
                    segmentation_indices: enhancedPolygons
                })
            });
            
            const data = await response.json();
            
            clearInterval(progressInterval);
            setSaveProgress(100);
            
            if (data.success) {
                setToastMessage('Segmentation saved successfully!');
                setShowToast(true);
                setImageData(prev => ({
                    ...prev,
                    segmentation_url: data.segmentation_url,
                    segmentation_indices_array: data.segmentation_indices_array
                }));
            } else {
                throw new Error(data.error || 'Save failed');
            }
        } catch (error) {
            setError(error.message || 'Failed to save segmentation');
        } finally {
            setTimeout(() => {
                setIsSaving(false);
                setSaveProgress(0);
            }, 500);
        }
    };

    const getDiatomLabel = (value) => {
        const labels = {
            0: 'Incomplete Diatom',
            1: 'Complete Diatom',
            2: 'Fragment Diatom',
            3: 'Blurred Diatom',
            4: 'Diatom SideView'
        };
        return labels[value] || 'Unknown';
    };

    const handleKeyPress = (e) => {
        if (e.key === 'Escape' && isDrawing) {
            setCurrentPolygon([]);
            setIsDrawing(false);
        }
    };

    const handlePrevious = () => {
        setImageIndex(prev => Math.max(0, prev - 1));
    };

    const handleNext = () => {
        setImageIndex(prev => Math.min(totalImages - 1, prev + 1));
    };

    const handleMouseMove = (e) => {
        if (!isDrawing || !canvasRef.current) return;
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Redraw existing polygons
        polygons.forEach(polygon => {
            if (polygon.points.length < 3) return;
            ctx.beginPath();
            ctx.moveTo(polygon.points[0].x, polygon.points[0].y);
            polygon.points.forEach(point => {
                ctx.lineTo(point.x, point.y);
            });
            ctx.closePath();
            ctx.strokeStyle = polygon.color;
            ctx.lineWidth = 2;
            ctx.stroke();
            ctx.fillStyle = `${polygon.color}40`;
            ctx.fill();
        });

        // Draw current polygon
        if (currentPolygon.length > 0) {
            ctx.beginPath();
            ctx.moveTo(currentPolygon[0].x, currentPolygon[0].y);
            currentPolygon.forEach(point => {
                ctx.lineTo(point.x, point.y);
            });
            ctx.strokeStyle = '#2ecc71';
            ctx.lineWidth = 2;
            ctx.stroke();
        }
    };

    useEffect(() => {
        document.addEventListener('keydown', handleKeyPress);
        return () => {
            document.removeEventListener('keydown', handleKeyPress);
        };
    }, [isDrawing]);

    return (
        <div className="flex h-screen bg-gray-200">
            {/* Left Sidebar */}
            <div className="w-64 bg-gray-800 fixed h-full">
                <img 
                    src="/static/diatomhub-images/logo/diatom_hub_5e.svg" 
                    alt="DiatomHub Logo" 
                    className="w-4/5 mx-auto mt-5"
                />
                
                <div className="flex flex-col gap-3 px-4 mt-6">
                    <a href="/modules" 
                       className="px-4 py-3 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors duration-200">
                        View Installed Modules
                    </a>
                    <a href="/all_papers" 
                       className="px-4 py-3 text-sm font-medium text-white bg-transparent border border-white rounded-md hover:bg-white/10 transition-colors duration-200">
                        View Papers
                    </a>
                    <a href="/diatoms_data" 
                       className="px-4 py-3 text-sm font-medium text-white bg-transparent border border-white rounded-md hover:bg-white/10 transition-colors duration-200">
                        View Diatoms Data
                    </a>
                    <a href="/label" 
                       className="px-4 py-3 text-sm font-medium text-white bg-transparent border border-white rounded-md hover:bg-white/10 transition-colors duration-200">
                        Label Images
                    </a>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 ml-64 mr-96">
                <div className="flex flex-col items-center justify-center min-h-screen p-5">
                    <div className="text-4xl font-bold mb-4 text-gray-800">
                        Diatom Segmentation
                    </div>
                    
                    <DiatomSelector 
                        selected={selectedType}
                        setSelected={setSelectedType}
                    />
                    
                    <Canvas
                        imageUrl={imageUrl}
                        polygons={polygons}
                        currentPolygon={currentPolygon}
                        selectedSegmentIndex={selectedSegmentIndex}
                        isDrawing={isDrawing}
                        onCanvasClick={handleCanvasClick}
                        onMouseMove={handleMouseMove}
                        getDiatomLabel={getDiatomLabel}
                        containerRef={containerRef}
                        canvasRef={canvasRef}
                        imageRef={imageRef}
                    />
                    
                    <div className="flex justify-center space-x-4 mt-6">
                        <button 
                            onClick={handlePrevious}
                            disabled={imageIndex === 0}
                            className="bg-yellow-400 text-black px-8 py-3 rounded-lg font-bold disabled:opacity-50 transform transition-all duration-200 hover:scale-105 hover:bg-yellow-300 hover:shadow-lg"
                        >
                            Previous
                        </button>
                        
                        <SegmentationButtons 
                            onSave={() => handleSave()}
                            onUpdate={handleUpdateSegmentations}
                            onDownload={() => window.location.href = '/api/download_segmentation'}
                            isSaving={isSaving}
                            isUpdating={isUpdating}
                            saveProgress={saveProgress}
                            hasSegmentations={polygons.length > 0}
                        />
                        
                        <button 
                            onClick={handleNext}
                            disabled={imageIndex === totalImages - 1}
                            className="bg-yellow-400 text-black px-8 py-3 rounded-lg font-bold disabled:opacity-50 transform transition-all duration-200 hover:scale-105 hover:bg-yellow-300 hover:shadow-lg"
                        >
                            Next
                        </button>
                    </div>
                </div>
            </div>

            {/* Right Sidebar */}
            <Sidebar 
                polygons={polygons}
                selectedIndex={selectedSegmentIndex}
                onSelectSegment={setSelectedSegmentIndex}
                getDiatomLabel={getDiatomLabel}
            />

            {/* Notifications */}
            {error && (
                <div className="fixed top-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg">
                    {error}
                </div>
            )}
            
            {showToast && (
                <Toast 
                    message={toastMessage} 
                    onClose={() => setShowToast(false)} 
                />
            )}
        </div>
    );
};

// Render the application
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);