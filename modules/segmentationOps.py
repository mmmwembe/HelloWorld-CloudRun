import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

class SegmentationOps:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def normalize_coordinates(self, x: float, y: float, image_width: float, image_height: float) -> Tuple[float, float]:
        """
        Convert actual coordinates to normalized (0-1) range.
        """
        try:
            norm_x = x / image_width
            norm_y = y / image_height
            return (norm_x, norm_y)
        except Exception as e:
            self.logger.error(f"Error normalizing coordinates: {str(e)}")
            return (0.0, 0.0)

    def denormalize_coordinates(self, norm_x: float, norm_y: float, image_width: float, image_height: float) -> Tuple[float, float]:
        """
        Convert normalized coordinates to actual image coordinates.
        """
        try:
            x = norm_x * image_width
            y = norm_y * image_height
            return (x, y)
        except Exception as e:
            self.logger.error(f"Error denormalizing coordinates: {str(e)}")
            return (0.0, 0.0)

    def parse_segmentation_line(self, line: str) -> Tuple[int, str]:
        """
        Parse segmentation line into label and points string.
        """
        try:
            parts = line.strip().split(' ')
            if len(parts) < 3:
                return (None, "")
            
            label = int(parts[0])
            points_string = ' '.join(parts[1:])
            return (label, points_string)
        except Exception as e:
            self.logger.error(f"Error parsing segmentation line: {str(e)}")
            return (None, "")

    def parse_segmentation_file(self, file_content: str) -> List[Dict[str, Any]]:
        """
        Parse entire segmentation file into structured data.
        """
        try:
            segmentations = []
            lines = file_content.strip().split('\n')
            
            for idx, line in enumerate(lines):
                label, points_string = self.parse_segmentation_line(line)
                if label is not None:
                    segmentations.append({
                        'index': idx,
                        'label': label,
                        'points_string': points_string,
                        'points_count': len(points_string.split()) // 2
                    })
            
            return segmentations
        except Exception as e:
            self.logger.error(f"Error parsing segmentation file: {str(e)}")
            return []

    def calculate_bbox_overlap(self, points: List[str], bbox: str, image_width: float, image_height: float) -> float:
        """
        Calculate percentage of points that fall within bbox.
        """
        try:
            if not points or not bbox:
                return 0.0

            bbox_coords = [float(x) for x in bbox.split(',')]
            x1, y1, x2, y2 = bbox_coords
            
            points_inside = 0
            total_points = len(points) // 2
            
            for i in range(0, len(points), 2):
                norm_x = float(points[i])
                norm_y = float(points[i + 1])
                x, y = self.denormalize_coordinates(norm_x, norm_y, image_width, image_height)
                
                if x1 <= x <= x2 and y1 <= y <= y2:
                    points_inside += 1
            
            return points_inside / total_points if total_points > 0 else 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating bbox overlap: {str(e)}")
            return 0.0

    def validate_segmentation_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate segmentation data structure.
        """
        try:
            required_fields = ['segmentation_points', 'label', 'index']
            if not all(field in data for field in required_fields):
                return False
            
            points = data['segmentation_points'].split()
            if len(points) < 4 or len(points) % 2 != 0:  # Need at least 2 points
                return False
                
            try:
                [float(p) for p in points]  # Validate all points are numbers
            except ValueError:
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating segmentation data: {str(e)}")
            return False

    def find_matching_bbox(self, points_string: str, bboxes: List[Dict[str, Any]], 
                         image_width: float, image_height: float, threshold: float = 0.5) -> Optional[Dict[str, Any]]:
        """
        Find bbox that best encloses the segmentation points.
        """
        try:
            points = points_string.split()
            max_overlap = threshold
            best_bbox = None
            
            for bbox in bboxes:
                overlap = self.calculate_bbox_overlap(
                    points, 
                    bbox['bbox'], 
                    image_width, 
                    image_height
                )
                
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_bbox = bbox
            
            return best_bbox
            
        except Exception as e:
            self.logger.error(f"Error finding matching bbox: {str(e)}")
            return None

    def get_label_text(self, label: int) -> str:
        """
        Convert numeric label to text description.
        """
        label_map = {
            0: "Incomplete Diatom",
            1: "Complete Diatom",
            2: "Fragmented Diatom",
            3: "Blurred Diatom",
            4: "Diatom SideView"
        }
        return label_map.get(label, "Unknown")

    # def process_image_segmentations(self, image_data: Dict[str, Any], segmentation_text: str) -> Dict[str, Any]:
    #     """
    #     Process and align segmentations with bboxes for an image.
    #     """
    #     try:
    #         if not segmentation_text or not image_data.get('segmentation_indices_array'):
    #             return image_data
                
    #         image_width = float(image_data.get('image_width', 1024))
    #         image_height = float(image_data.get('image_height', 768))
    #         bboxes = image_data.get('info', [])
            
    #         # Parse segmentations
    #         segmentations = self.parse_segmentation_file(segmentation_text)
            
    #         # Process each segmentation
    #         for seg in segmentations:
    #             # Find corresponding entry in segmentation_indices_array
    #             seg_dict = next((s for s in image_data['segmentation_indices_array'] 
    #                            if s['index'] == seg['index']), None)
                
    #             if not seg_dict:
    #                 continue
                
    #             # Update segmentation data
    #             seg_dict['segmentation_points'] = seg['points_string']
    #             seg_dict['points_count'] = seg['points_count']
                
    #             # Find matching bbox
    #             matching_bbox = self.find_matching_bbox(
    #                 seg['points_string'],
    #                 bboxes,
    #                 image_width,
    #                 image_height
    #             )
                
    #             if matching_bbox:
    #                 seg_dict['bbox'] = matching_bbox['bbox']
    #                 seg_dict['yolo_bbox'] = matching_bbox['yolo_bbox']
    #                 seg_dict['species'] = matching_bbox.get('species', '')
                    
    #                 self.logger.info(f"Matched segmentation {seg['index']} to bbox for species {matching_bbox.get('species', '')}")
    #             else:
    #                 # Clear bbox-related fields if no match found
    #                 seg_dict['bbox'] = ""
    #                 seg_dict['yolo_bbox'] = ""
    #                 seg_dict['species'] = ""
            
    #         return image_data
            
    #     except Exception as e:
    #         self.logger.error(f"Error processing image segmentations: {str(e)}")
    #         return image_data
        
        
        
    def process_image_segmentations(self, image_data: Dict[str, Any], segmentation_text: str) -> Dict[str, Any]:
        """
        Process and align segmentations with bboxes for an image.
        """
        try:
            if not segmentation_text or 'segmentation_indices_array' not in image_data:
                return image_data
                
            image_width = float(image_data.get('image_width', 1024))
            image_height = float(image_data.get('image_height', 768))
            bboxes = image_data.get('info', [])
            
            # Parse segmentations
            segmentations = self.parse_segmentation_file(segmentation_text)
            
            # Process each segmentation
            for seg in segmentations:
                # Find corresponding entry in segmentation_indices_array
                seg_dict = next((s for s in image_data['segmentation_indices_array'] 
                            if s['index'] == seg['index']), None)
                
                if not seg_dict:
                    continue
                
                # Update segmentation data
                seg_dict['segmentation_points'] = seg['points_string']
                seg_dict['points_count'] = seg['points_count']
                
                # Calculate denormalized points
                points = seg['points_string'].split()
                denormalized = []
                for i in range(0, len(points), 2):
                    x = float(points[i]) * image_width
                    y = float(points[i + 1]) * image_height
                    denormalized.extend([str(round(x)), str(round(y))])
                seg_dict['denormalized_segmentation_points'] = ' '.join(denormalized)
                
                # Initialize default values
                seg_dict['bbox'] = ""
                seg_dict['yolo_bbox'] = ""
                seg_dict['species'] = ""
                
                # Find matching bbox using denormalized points
                points_array = [float(p) for p in denormalized]
                max_overlap = 0
                matching_bbox = None
                
                for bbox in bboxes:
                    x1, y1, x2, y2 = map(float, bbox['bbox'].split(','))
                    
                    # Count points inside bbox
                    points_inside = 0
                    total_points = len(points_array) // 2
                    
                    for point_idx in range(0, len(points_array), 2):
                        x = points_array[point_idx]
                        y = points_array[point_idx + 1]
                        
                        if x1 <= x <= x2 and y1 <= y <= y2:
                            points_inside += 1
                    
                    overlap = points_inside / total_points if total_points > 0 else 0
                    
                    if overlap > max_overlap and overlap >= 0.5:  # At least 50% of points should be inside
                        max_overlap = overlap
                        matching_bbox = bbox
                
                if matching_bbox:
                    seg_dict['bbox'] = matching_bbox['bbox']
                    seg_dict['yolo_bbox'] = matching_bbox['yolo_bbox']
                    seg_dict['species'] = matching_bbox.get('species', '')
                    self.logger.info(f"Matched segmentation {seg['index']} to bbox for species {matching_bbox.get('species', '')}")
            
            return image_data
            
        except Exception as e:
            self.logger.error(f"Error processing image segmentations: {str(e)}")
            return image_data