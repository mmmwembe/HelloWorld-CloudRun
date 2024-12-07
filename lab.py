{
  "papers_json_public_url": "https://storage.googleapis.com/papers-diatoms-jsons/jsons_from_pdfs/eb9db0ca54e94dbc82cffdab497cde13/eb9db0ca54e94dbc82cffdab497cde13.json",
  "diatoms_data": {
    "image_url": "https://storage.googleapis.com/papers-extracted-images-bucket-mmm/eb9db0ca54e94dbc82cffdab497cde13/4791b986db08dd6602849ec25d1b75fed1f67dbabd8b021d79d9df370240fb2c_image_1.jpeg",
    "image_width": "1024",
    "image_height": "768",
    "info": [
      {
        "bbox": "36.5,26,247.5,437",
        "embeddings": "",
        "index": 14,
        "label": [
          "14 Lyrella_spectabilis"
        ],
        "segmentation": "",
        "species": "Lyrella_spectabilis",
        "yolo_bbox": "1 0.042099 0.049785 0.062556 0.088387"
      },
      {
        "bbox": "250.5,24,463.5,422",
        "embeddings": "",
        "index": 15,
        "label": [
          "15 Navicula_hennedyi_fo_granulata"
        ],
        "segmentation": "",
        "species": "Navicula_hennedyi_fo_granulata",
        "yolo_bbox": "1 0.105840 0.047957 0.063149 0.085591"
      },
      {
        "bbox": "145.5,436,251.5,686",
        "embeddings": "",
        "index": 17,
        "label": [
          "17 Lyrella_hennedyi"
        ],
        "segmentation": "",
        "species": "Lyrella_hennedyi",
        "yolo_bbox": "1 0.058850 0.120645 0.031426 0.053763"
      }
    ],
    "segmentation_url": "https://storage.googleapis.com/papers-diatoms-segmentation/eb9db0ca54e94dbc82cffdab497cde13/4791b986db08dd6602849ec25d1b75fed1f67dbabd8b021d79d9df370240fb2c_image_1.txt",
    "segmentation_indices_array": [
      {
        "index": 0,
        "label": 1,
        "points_count": 19,
        "label_text": "Incomplete Diatom"
      },
      {
        "index": 1,
        "label": 1,
        "points_count": 23,
        "label_text": "Incomplete Diatom"
      },
      {
        "index": 2,
        "label": 1,
        "points_count": 18,
        "label_text": "Incomplete Diatom"
      }
    ]
  },
  "citation": {
    "authors": [
      "S.R. Stidolph",
      "F.A.S. Sterrenburg",
      "K.E.L. Smith",
      "A. Kraberg"
    ],
    "year": "2012",
    "title": "Stuart R. Stidolph Diatom Atlas",
    "type": "report",
    "journal_name": "",
    "journal_volume": "",
    "journal_issue": "",
    "journal_pages": "199",
    "org_name": "U.S. Geological Survey",
    "org_report_number": "Open-File Report 2012-1163",
    "digital_doi": "",
    "digital_url": "http://pubs.usgs.gov/of/2012/1163/",
    "formatted_citation": "Stidolph, S.R., Sterrenburg, F.A.S., Smith, K.E.L., Kraberg, A., 2012, Stuart R. Stidolph Diatom Atlas: U.S. Geological Survey Open-File Report 2012-1163, 199 p., available at http://pubs.usgs.gov/of/2012/1163/"
  }
}


# @app.route('/api/save_segmentation', methods=['POST'])
# def save_segmentation():
#     """Save segmentation data and indices array to GCS bucket and update DIATOMS_DATA"""
#     try:
#         data = request.json
#         image_index = data.get('image_index', 0)
#         segmentation_data = data.get('segmentation_data', '')
#         image_filename = data.get('image_filename', '')
#         segmentation_indices = data.get('segmentation_indices', [])
        
#         logger.info(f"Saving segmentation for image {image_filename}")
#         logger.debug(f"Segmentation data: {segmentation_data}")
#         logger.debug(f"Segmentation indices: {segmentation_indices}")
        
#         if not segmentation_data or not image_filename:
#             raise ValueError("Missing required data")
            
#         # Save segmentation data to GCS bucket
#         segmentation_url = gcp_ops.save_segmentation_data(
#             segmentation_data=segmentation_data,
#             image_filename=image_filename,
#             session_id=SESSION_ID,
#             bucket_name=BUCKET_SEGMENTATION_LABELS
#         )
        
#         if not segmentation_url:
#             raise Exception("Failed to save segmentation data to GCS")
        
#         logger.info(f"Saved segmentation to URL: {segmentation_url}")
            
#         # Update DIATOMS_DATA with segmentation URL and indices array
#         if 0 <= image_index < len(DIATOMS_DATA):
#             DIATOMS_DATA[image_index]['segmentation_url'] = segmentation_url
#             DIATOMS_DATA[image_index]['segmentation_indices_array'] = segmentation_indices
            
#             # Store canvas dimensions if not present
#             if 'canvasWidth' not in DIATOMS_DATA[image_index]:
#                 DIATOMS_DATA[image_index]['canvasWidth'] = DIATOMS_DATA[image_index].get('image_width')
#             if 'canvasHeight' not in DIATOMS_DATA[image_index]:
#                 DIATOMS_DATA[image_index]['canvasHeight'] = DIATOMS_DATA[image_index].get('image_height')
            
#             # Update corresponding entry in PAPER_JSON_FILES
#             for paper in PAPER_JSON_FILES:
#                 if 'diatoms_data' in paper:
#                     if isinstance(paper['diatoms_data'], str):
#                         paper['diatoms_data'] = json.loads(paper['diatoms_data'])
                    
#                     if paper['diatoms_data'].get('image_url') == DIATOMS_DATA[image_index].get('image_url'):
#                         paper['diatoms_data'].update({
#                             'segmentation_url': segmentation_url,
#                             'segmentation_indices_array': segmentation_indices,
#                             'canvasWidth': DIATOMS_DATA[image_index].get('canvasWidth'),
#                             'canvasHeight': DIATOMS_DATA[image_index].get('canvasHeight')
#                         })
#                         break
            
#             # Save updated data to GCS
#             success = ClaudeAI.update_and_save_papers(
#                 PAPERS_JSON_PUBLIC_URL,
#                 PAPER_JSON_FILES,
#                 DIATOMS_DATA
#             )
            
#             if not success:
#                 raise Exception("Failed to update papers data in GCS")
                
#             return jsonify({
#                 'success': True,
#                 'message': 'Segmentation saved successfully',
#                 'segmentation_url': segmentation_url,
#                 'segmentation_indices_array': segmentation_indices
#             })
#         else:
#             raise ValueError(f"Invalid image index: {image_index}")
            
#     except Exception as e:
#         logger.error(f"Error saving segmentation: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500
# @app.route('/api/save_segmentation', methods=['POST'])
# def save_segmentation():
#     """Save segmentation data and indices array to GCS bucket and update DIATOMS_DATA"""
#     try:
#         data = request.json
#         if not data:
#             return jsonify({
#                 'success': False,
#                 'error': 'No JSON data received'
#             }), 400

#         image_index = data.get('image_index', 0)
#         segmentation_data = data.get('segmentation_data', '')
#         image_filename = data.get('image_filename', '')
#         canvas_dimensions = data.get('canvas_dimensions', {})
        
#         logger.info(f"Saving segmentation for image {image_filename}")
#         logger.debug(f"Canvas dimensions: {canvas_dimensions}")
        
#         # Update DIATOMS_DATA with canvas dimensions
#         if 0 <= image_index < len(DIATOMS_DATA):
#             if canvas_dimensions:
#                 DIATOMS_DATA[image_index]['canvasWidth'] = canvas_dimensions.get('width')
#                 DIATOMS_DATA[image_index]['canvasHeight'] = canvas_dimensions.get('height')
            
#             # Only proceed with segmentation save if we have data
#             if segmentation_data and image_filename:
#                 segmentation_url = gcp_ops.save_segmentation_data(
#                     segmentation_data=segmentation_data,
#                     image_filename=image_filename,
#                     session_id=SESSION_ID,
#                     bucket_name=BUCKET_SEGMENTATION_LABELS
#                 )
                
#                 if segmentation_url:
#                     DIATOMS_DATA[image_index]['segmentation_url'] = segmentation_url
            
#             # Update corresponding entry in PAPER_JSON_FILES
#             for paper in PAPER_JSON_FILES:
#                 if 'diatoms_data' in paper:
#                     if isinstance(paper['diatoms_data'], str):
#                         paper['diatoms_data'] = json.loads(paper['diatoms_data'])
                    
#                     if paper['diatoms_data'].get('image_url') == DIATOMS_DATA[image_index].get('image_url'):
#                         if canvas_dimensions:
#                             paper['diatoms_data'].update({
#                                 'canvasWidth': canvas_dimensions.get('width'),
#                                 'canvasHeight': canvas_dimensions.get('height')
#                             })
#                         break
            
#             # Save updated data to GCS
#             success = ClaudeAI.update_and_save_papers(
#                 PAPERS_JSON_PUBLIC_URL,
#                 PAPER_JSON_FILES,
#                 DIATOMS_DATA
#             )
            
#             if not success:
#                 raise Exception("Failed to update papers data in GCS")
            
#             return jsonify({
#                 'success': True,
#                 'message': 'Data saved successfully'
#             })
#         else:
#             raise ValueError(f"Invalid image index: {image_index}")
            
#     except Exception as e:
#         logger.error(f"Error saving segmentation: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500
# Add to app.py

# @app.route('/api/save_segmentation', methods=['POST'])
# def save_segmentation():
#     """Save segmentation data with enhanced structure"""
#     try:
#         data = request.json
#         image_index = data.get('image_index', 0)
#         segmentation_data = data.get('segmentation_data', '')
#         image_filename = data.get('image_filename', '')
#         segmentation_indices = data.get('segmentation_indices', [])
        
#         logger.info(f"Processing save request for image {image_filename}")
        
#         if not segmentation_data or not image_filename:
#             raise ValueError("Missing required data")
            
#         # Save segmentation data to GCS bucket
#         segmentation_url = gcp_ops.save_segmentation_data(
#             segmentation_data=segmentation_data,
#             image_filename=image_filename,
#             session_id=SESSION_ID,
#             bucket_name=BUCKET_SEGMENTATION_LABELS
#         )
        
#         if not segmentation_url:
#             raise Exception("Failed to save segmentation data to GCS")
            
#         # Update DIATOMS_DATA with enhanced data
#         if 0 <= image_index < len(DIATOMS_DATA):
#             current_image = DIATOMS_DATA[image_index]
#             image_width = current_image.get('image_width')
#             image_height = current_image.get('image_height')
            
#             # Process and enhance segmentation indices
#             enhanced_indices = []
#             for segment in segmentation_indices:
#                 points = segment.get('points', [])
#                 if not points:
#                     continue
                    
#                 # Extract existing data
#                 segment_data = {
#                     'label': segment.get('label', 0),
#                     'points': points,
#                     'color': segment.get('color', '#2ecc71')
#                 }
                
#                 # Calculate normalized coordinates
#                 norm_points = [
#                     {
#                         'x': point['x'] / image_width,
#                         'y': point['y'] / image_height
#                     }
#                     for point in points
#                 ]
                
#                 # Calculate arrays and bounding boxes
#                 denorm_xs = [p['x'] for p in points]
#                 denorm_ys = [p['y'] for p in points]
                
#                 top_left = {
#                     'x': min(denorm_xs),
#                     'y': min(denorm_ys)
#                 }
                
#                 bottom_right = {
#                     'x': max(denorm_xs),
#                     'y': max(denorm_ys)
#                 }
                
#                 # Calculate width and height
#                 width = bottom_right['x'] - top_left['x']
#                 height = bottom_right['y'] - top_left['y']
                
#                 # Calculate center points
#                 center_x = top_left['x'] + width / 2
#                 center_y = top_left['y'] + height / 2
                
#                 # Add enhanced data
#                 segment_data.update({
#                     'norm_polygon_points': norm_points,
#                     'denorm_polygon_points': points,
#                     'denorm_xs': denorm_xs,
#                     'denorm_ys': denorm_ys,
#                     'denorm_top_left': top_left,
#                     'denorm_bottom_right': bottom_right,
#                     'denorm_bbox': f"{top_left['x']},{top_left['y']} {bottom_right['x']},{bottom_right['y']}",
#                     'denorm_calculated_yolobbox': [
#                         center_x / image_width,
#                         center_y / image_height,
#                         width / image_width,
#                         height / image_height
#                     ],
#                     'image_width': image_width,
#                     'image_height': image_height
#                 })
                
#                 enhanced_indices.append(segment_data)
            
#             # Update current image data
#             current_image['segmentation_url'] = segmentation_url
#             current_image['segmentation_indices_array'] = enhanced_indices
            
#             # Store canvas dimensions if not present
#             if 'canvasWidth' not in current_image:
#                 current_image['canvasWidth'] = image_width
#             if 'canvasHeight' not in current_image:
#                 current_image['canvasHeight'] = image_height
            
#             # Update DIATOMS_DATA
#             DIATOMS_DATA[image_index] = current_image
            
#             # Update corresponding entry in PAPER_JSON_FILES
#             for paper in PAPER_JSON_FILES:
#                 if 'diatoms_data' in paper:
#                     if isinstance(paper['diatoms_data'], str):
#                         paper['diatoms_data'] = json.loads(paper['diatoms_data'])
                    
#                     if paper['diatoms_data'].get('image_url') == current_image.get('image_url'):
#                         paper['diatoms_data'] = current_image
#                         break
            
#             # Save updated data to GCS
#             success = ClaudeAI.update_and_save_papers(
#                 PAPERS_JSON_PUBLIC_URL,
#                 PAPER_JSON_FILES,
#                 DIATOMS_DATA
#             )
            
#             if not success:
#                 raise Exception("Failed to update papers data in GCS")
                
#             return jsonify({
#                 'success': True,
#                 'message': 'Segmentation saved successfully',
#                 'segmentation_url': segmentation_url,
#                 'segmentation_indices_array': enhanced_indices
#             })
#         else:
#             raise ValueError(f"Invalid image index: {image_index}")
            
#     except Exception as e:
#         logger.error(f"Error saving segmentation: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500
