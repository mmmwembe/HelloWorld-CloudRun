// static/react/js/utils/polygon-utils.js

// Calculate enhanced data for a polygon
export const calculatePolygonData = (points, imageWidth, imageHeight) => {
    // Extract x and y coordinates
    const denormXs = points.map(p => p.x);
    const denormYs = points.map(p => p.y);
    
    // Calculate bounding points
    const topLeft = {
        x: Math.min(...denormXs),
        y: Math.min(...denormYs)
    };
    
    const bottomRight = {
        x: Math.max(...denormXs),
        y: Math.max(...denormYs)
    };
    
    // Calculate dimensions
    const width = bottomRight.x - topLeft.x;
    const height = bottomRight.y - topLeft.y;
    const centerX = topLeft.x + width / 2;
    const centerY = topLeft.y + height / 2;
    
    // Create normalized points
    const normalizedPoints = points.map(point => ({
        x: point.x / imageWidth,
        y: point.y / imageHeight
    }));
    
    // Create YOLO format bbox
    const yoloBBox = [
        centerX / imageWidth,
        centerY / imageHeight,
        width / imageWidth,
        height / imageHeight
    ];
    
    return {
        norm_polygon_points: normalizedPoints,
        denorm_polygon_points: points,
        denorm_xs: denormXs,
        denorm_ys: denormYs,
        denorm_top_left: topLeft,
        denorm_bottom_right: bottomRight,
        denorm_bbox: `${topLeft.x},${topLeft.y} ${bottomRight.x},${bottomRight.y}`,
        denorm_calculated_yolobbox: yoloBBox,
        image_width: imageWidth,
        image_height: imageHeight
    };
};

// Process and enhance existing segmentations
export const processExistingSegmentations = (segmentationIndices, imageWidth, imageHeight) => {
    return segmentationIndices.map(segment => {
        const points = segment.points || [];
        const enhancedData = calculatePolygonData(points, imageWidth, imageHeight);
        return { ...segment, ...enhancedData };
    });
};

// Generate segmentation text from polygons
export const generateSegmentationText = (polygons, imageWidth, imageHeight) => {
    return polygons.map(polygon => {
        const normalizedPoints = polygon.points.map(point => {
            const x = point.x / imageWidth;
            const y = point.y / imageHeight;
            return `${x.toFixed(6)} ${y.toFixed(6)}`;
        }).join(' ');
        return `${polygon.label} ${normalizedPoints}`;
    }).join('\n');
};

// Parse segmentation text into polygon data
export const parseSegmentationText = (text, imageWidth, imageHeight) => {
    if (!text.trim()) return [];
    
    return text.trim().split('\n').map(line => {
        const [label, ...coords] = line.split(' ');
        const points = [];
        
        for (let i = 0; i < coords.length; i += 2) {
            if (coords[i] && coords[i+1]) {
                points.push({
                    x: parseFloat(coords[i]) * imageWidth,
                    y: parseFloat(coords[i+1]) * imageHeight
                });
            }
        }
        
        return {
            label: parseInt(label),
            points,
            color: getRandomColor()
        };
    }).filter(polygon => polygon.points.length >= 3);
};

// Generate random color for polygons
export const getRandomColor = () => {
    const colors = ['#2ecc71', '#e74c3c', '#3498db', '#f1c40f', '#9b59b6', '#1abc9c'];
    return colors[Math.floor(Math.random() * colors.length)];
};