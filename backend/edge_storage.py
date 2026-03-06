"""
YieldVision Edge Storage System
JSON edge storage + PostgreSQL cloud synchronization
"""

import json
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import os
import threading
import logging
from pathlib import Path

class EdgeStorageManager:
    """Manages edge JSON storage with PostgreSQL cloud sync"""
    
    def __init__(self, edge_storage_path: str = "edge_storage", 
                 cloud_db_config: Optional[Dict] = None):
        self.edge_storage_path = Path(edge_storage_path)
        self.edge_storage_path.mkdir(exist_ok=True)
        
        # Edge SQLite database for local operations
        self.edge_db_path = self.edge_storage_path / "edge_data.db"
        self.edge_conn = sqlite3.connect(str(self.edge_db_path), check_same_thread=False)
        self.edge_conn.row_factory = sqlite3.Row
        
        # Cloud PostgreSQL configuration
        self.cloud_db_config = cloud_db_config
        self.cloud_conn = None
        
        # Initialize edge database schema
        self._init_edge_schema()
        
        # Sync configuration
        self.sync_interval = 300  # 5 minutes
        self.sync_thread = None
        self.sync_running = False
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def _init_edge_schema(self):
        """Initialize SQLite schema for edge storage"""
        cursor = self.edge_conn.cursor()
        
        # Zones table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS zones (
                zone_id TEXT PRIMARY KEY,
                center_lat REAL,
                center_lon REAL,
                area_m2 REAL,
                soil_type TEXT,
                slope_percent REAL,
                aspect_degrees REAL,
                drainage_rate TEXT,
                created_at TIMESTAMP,
                synced_at TIMESTAMP,
                is_synced BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Sensor readings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id TEXT,
                timestamp TIMESTAMP,
                gps_lat REAL,
                gps_lon REAL,
                soil_moisture_5cm REAL,
                soil_moisture_20cm REAL,
                soil_moisture_50cm REAL,
                nitrogen_ppm REAL,
                phosphorus_ppm REAL,
                potassium_ppm REAL,
                ph_level REAL,
                soil_temperature_c REAL,
                air_temperature_c REAL,
                humidity_percent REAL,
                solar_radiation_wm2 REAL,
                electrical_conductivity REAL,
                organic_matter_percent REAL,
                synced_at TIMESTAMP,
                is_synced BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (zone_id) REFERENCES zones (zone_id)
            )
        """)
        
        # Decisions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id TEXT,
                action_type TEXT,
                action_amount REAL,
                expected_yield_kg REAL,
                net_benefit_usd REAL,
                roi_multiplier REAL,
                confidence_score REAL,
                risk_level TEXT,
                recommendation TEXT,
                created_at TIMESTAMP,
                synced_at TIMESTAMP,
                is_synced BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (zone_id) REFERENCES zones (zone_id)
            )
        """)
        
        # Sync status table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                last_sync TIMESTAMP,
                records_synced INTEGER,
                sync_errors TEXT,
                sync_status TEXT
            )
        """)
        
        self.edge_conn.commit()
    
    def connect_cloud_db(self):
        """Connect to PostgreSQL cloud database"""
        if not self.cloud_db_config:
            self.logger.warning("No cloud database configuration provided")
            return False
        
        try:
            self.cloud_conn = psycopg2.connect(
                host=self.cloud_db_config['host'],
                database=self.cloud_db_config['database'],
                user=self.cloud_db_config['user'],
                password=self.cloud_db_config['password'],
                port=self.cloud_db_config.get('port', 5432)
            )
            self.logger.info("Connected to PostgreSQL cloud database")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to cloud database: {e}")
            return False
    
    def store_zone(self, zone_data: Dict) -> bool:
        """Store zone data locally on edge"""
        try:
            cursor = self.edge_conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO zones 
                (zone_id, center_lat, center_lon, area_m2, soil_type, 
                 slope_percent, aspect_degrees, drainage_rate, created_at, is_synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
            """, (
                zone_data['zone_id'],
                zone_data['center_lat'],
                zone_data['center_lon'],
                zone_data.get('area_m2', 4.0),
                zone_data.get('soil_type', 'unknown'),
                zone_data.get('slope_percent', 0.0),
                zone_data.get('aspect_degrees', 0),
                zone_data.get('drainage_rate', 'medium'),
                datetime.now()
            ))
            self.edge_conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error storing zone: {e}")
            return False
    
    def store_sensor_reading(self, reading_data: Dict) -> bool:
        """Store sensor reading locally on edge"""
        try:
            cursor = self.edge_conn.cursor()
            cursor.execute("""
                INSERT INTO sensor_readings 
                (zone_id, timestamp, gps_lat, gps_lon, soil_moisture_5cm,
                 soil_moisture_20cm, soil_moisture_50cm, nitrogen_ppm, phosphorus_ppm,
                 potassium_ppm, ph_level, soil_temperature_c, air_temperature_c,
                 humidity_percent, solar_radiation_wm2, electrical_conductivity,
                 organic_matter_percent, is_synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
            """, (
                reading_data['zone_id'],
                reading_data.get('timestamp', datetime.now()),
                reading_data.get('gps_lat', 0.0),
                reading_data.get('gps_lon', 0.0),
                reading_data.get('soil_moisture_5cm', 0.0),
                reading_data.get('soil_moisture_20cm', 0.0),
                reading_data.get('soil_moisture_50cm', 0.0),
                reading_data.get('nitrogen_ppm', 0.0),
                reading_data.get('phosphorus_ppm', 0.0),
                reading_data.get('potassium_ppm', 0.0),
                reading_data.get('ph_level', 7.0),
                reading_data.get('soil_temperature_c', 25.0),
                reading_data.get('air_temperature_c', 25.0),
                reading_data.get('humidity_percent', 50.0),
                reading_data.get('solar_radiation_wm2', 400.0),
                reading_data.get('electrical_conductivity', 1.0),
                reading_data.get('organic_matter_percent', 2.0)
            ))
            self.edge_conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error storing sensor reading: {e}")
            return False
    
    def store_decision(self, decision_data: Dict) -> bool:
        """Store decision data locally on edge"""
        try:
            cursor = self.edge_conn.cursor()
            cursor.execute("""
                INSERT INTO decisions 
                (zone_id, action_type, action_amount, expected_yield_kg,
                 net_benefit_usd, roi_multiplier, confidence_score, risk_level,
                 recommendation, created_at, is_synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
            """, (
                decision_data['zone_id'],
                decision_data.get('action_type', ''),
                decision_data.get('action_amount', 0.0),
                decision_data.get('expected_yield_kg', 0.0),
                decision_data.get('net_benefit_usd', 0.0),
                decision_data.get('roi_multiplier', 0.0),
                decision_data.get('confidence_score', 0.0),
                decision_data.get('risk_level', 'unknown'),
                decision_data.get('recommendation', ''),
                decision_data.get('created_at', datetime.now())
            ))
            self.edge_conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error storing decision: {e}")
            return False
    
    def get_zone_data(self, zone_id: str) -> Optional[Dict]:
        """Get zone data from edge storage"""
        cursor = self.edge_conn.cursor()
        cursor.execute("SELECT * FROM zones WHERE zone_id = ?", (zone_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_latest_sensor_reading(self, zone_id: str) -> Optional[Dict]:
        """Get latest sensor reading for a zone"""
        cursor = self.edge_conn.cursor()
        cursor.execute("""
            SELECT * FROM sensor_readings 
            WHERE zone_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        """, (zone_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_sensor_readings_batch(self, zone_id: str, limit: int = 100) -> List[Dict]:
        """Get recent sensor readings for a zone"""
        cursor = self.edge_conn.cursor()
        cursor.execute("""
            SELECT * FROM sensor_readings 
            WHERE zone_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (zone_id, limit))
        return [dict(row) for row in cursor.fetchall()]
    
    def export_to_json(self, output_path: str = None) -> str:
        """Export all edge data to JSON file"""
        if not output_path:
            output_path = self.edge_storage_path / f"edge_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Collect all data
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'zones': [],
            'sensor_readings': [],
            'decisions': []
        }
        
        # Export zones
        cursor = self.edge_conn.cursor()
        cursor.execute("SELECT * FROM zones")
        export_data['zones'] = [dict(row) for row in cursor.fetchall()]
        
        # Export sensor readings
        cursor.execute("SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT 1000")
        export_data['sensor_readings'] = [dict(row) for row in cursor.fetchall()]
        
        # Export decisions
        cursor.execute("SELECT * FROM decisions ORDER BY created_at DESC LIMIT 500")
        export_data['decisions'] = [dict(row) for row in cursor.fetchall()]
        
        # Write to file
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        self.logger.info(f"Exported edge data to {output_path}")
        return str(output_path)
    
    def sync_to_cloud(self) -> Dict[str, Any]:
        """Sync local edge data to PostgreSQL cloud"""
        if not self.cloud_conn:
            if not self.connect_cloud_db():
                return {'status': 'error', 'message': 'No cloud connection'}
        
        sync_stats = {
            'zones_synced': 0,
            'readings_synced': 0,
            'decisions_synced': 0,
            'errors': []
        }
        
        try:
            cursor = self.edge_conn.cursor()
            cloud_cursor = self.cloud_conn.cursor()
            
            # Sync zones
            cursor.execute("SELECT * FROM zones WHERE is_synced = FALSE")
            zones_to_sync = cursor.fetchall()
            
            for zone_row in zones_to_sync:
                try:
                    zone_data = dict(zone_row)
                    cloud_cursor.execute("""
                        INSERT INTO zones 
                        (zone_id, center_lat, center_lon, area_m2, soil_type,
                         slope_percent, aspect_degrees, drainage_rate, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (zone_id) DO UPDATE SET
                        center_lat = EXCLUDED.center_lat,
                        center_lon = EXCLUDED.center_lon,
                        area_m2 = EXCLUDED.area_m2,
                        soil_type = EXCLUDED.soil_type,
                        slope_percent = EXCLUDED.slope_percent,
                        aspect_degrees = EXCLUDED.aspect_degrees,
                        drainage_rate = EXCLUDED.drainage_rate
                    """, (
                        zone_data['zone_id'], zone_data['center_lat'], zone_data['center_lon'],
                        zone_data['area_m2'], zone_data['soil_type'], zone_data['slope_percent'],
                        zone_data['aspect_degrees'], zone_data['drainage_rate'], zone_data['created_at']
                    ))
                    
                    # Mark as synced
                    cursor.execute("UPDATE zones SET is_synced = TRUE, synced_at = ? WHERE zone_id = ?",
                                 (datetime.now(), zone_data['zone_id']))
                    sync_stats['zones_synced'] += 1
                    
                except Exception as e:
                    sync_stats['errors'].append(f"Zone sync error: {e}")
            
            # Sync sensor readings
            cursor.execute("SELECT * FROM sensor_readings WHERE is_synced = FALSE LIMIT 100")
            readings_to_sync = cursor.fetchall()
            
            for reading_row in readings_to_sync:
                try:
                    reading_data = dict(reading_row)
                    cloud_cursor.execute("""
                        INSERT INTO sensor_readings 
                        (zone_id, timestamp, gps_lat, gps_lon, soil_moisture_5cm,
                         soil_moisture_20cm, soil_moisture_50cm, nitrogen_ppm, phosphorus_ppm,
                         potassium_ppm, ph_level, soil_temperature_c, air_temperature_c,
                         humidity_percent, solar_radiation_wm2, electrical_conductivity,
                         organic_matter_percent)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        reading_data['zone_id'], reading_data['timestamp'], reading_data['gps_lat'],
                        reading_data['gps_lon'], reading_data['soil_moisture_5cm'], reading_data['soil_moisture_20cm'],
                        reading_data['soil_moisture_50cm'], reading_data['nitrogen_ppm'], reading_data['phosphorus_ppm'],
                        reading_data['potassium_ppm'], reading_data['ph_level'], reading_data['soil_temperature_c'],
                        reading_data['air_temperature_c'], reading_data['humidity_percent'], reading_data['solar_radiation_wm2'],
                        reading_data['electrical_conductivity'], reading_data['organic_matter_percent']
                    ))
                    
                    cursor.execute("UPDATE sensor_readings SET is_synced = TRUE, synced_at = ? WHERE id = ?",
                                 (datetime.now(), reading_data['id']))
                    sync_stats['readings_synced'] += 1
                    
                except Exception as e:
                    sync_stats['errors'].append(f"Reading sync error: {e}")
            
            # Sync decisions
            cursor.execute("SELECT * FROM decisions WHERE is_synced = FALSE LIMIT 50")
            decisions_to_sync = cursor.fetchall()
            
            for decision_row in decisions_to_sync:
                try:
                    decision_data = dict(decision_row)
                    cloud_cursor.execute("""
                        INSERT INTO decisions 
                        (zone_id, action_type, action_amount, expected_yield_kg,
                         net_benefit_usd, roi_multiplier, confidence_score, risk_level,
                         recommendation, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        decision_data['zone_id'], decision_data['action_type'], decision_data['action_amount'],
                        decision_data['expected_yield_kg'], decision_data['net_benefit_usd'], decision_data['roi_multiplier'],
                        decision_data['confidence_score'], decision_data['risk_level'], decision_data['recommendation'],
                        decision_data['created_at']
                    ))
                    
                    cursor.execute("UPDATE decisions SET is_synced = TRUE, synced_at = ? WHERE id = ?",
                                 (datetime.now(), decision_data['id']))
                    sync_stats['decisions_synced'] += 1
                    
                except Exception as e:
                    sync_stats['errors'].append(f"Decision sync error: {e}")
            
            # Commit changes
            self.edge_conn.commit()
            self.cloud_conn.commit()
            
            # Record sync status
            cursor.execute("""
                INSERT INTO sync_status 
                (last_sync, records_synced, sync_errors, sync_status)
                VALUES (?, ?, ?, ?)
            """, (
                datetime.now(),
                sync_stats['zones_synced'] + sync_stats['readings_synced'] + sync_stats['decisions_synced'],
                json.dumps(sync_stats['errors']),
                'success' if not sync_stats['errors'] else 'partial'
            ))
            
            self.edge_conn.commit()
            
            self.logger.info(f"Sync completed: {sync_stats}")
            return {'status': 'success', 'stats': sync_stats}
            
        except Exception as e:
            self.logger.error(f"Sync failed: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def start_auto_sync(self):
        """Start automatic sync to cloud"""
        if self.sync_running:
            return
        
        self.sync_running = True
        self.sync_thread = threading.Thread(target=self._auto_sync_loop, daemon=True)
        self.sync_thread.start()
        self.logger.info("Auto-sync started")
    
    def stop_auto_sync(self):
        """Stop automatic sync to cloud"""
        self.sync_running = False
        if self.sync_thread:
            self.sync_thread.join()
        self.logger.info("Auto-sync stopped")
    
    def _auto_sync_loop(self):
        """Background sync loop"""
        while self.sync_running:
            try:
                self.sync_to_cloud()
                threading.Event().wait(self.sync_interval)
            except Exception as e:
                self.logger.error(f"Auto-sync error: {e}")
                threading.Event().wait(60)  # Wait 1 minute on error
    
    def get_sync_status(self) -> Dict:
        """Get current sync status"""
        cursor = self.edge_conn.cursor()
        cursor.execute("""
            SELECT * FROM sync_status 
            ORDER BY last_sync DESC 
            LIMIT 1
        """)
        last_sync = cursor.fetchone()
        
        # Get unsynced counts
        cursor.execute("SELECT COUNT(*) FROM zones WHERE is_synced = FALSE")
        unsynced_zones = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sensor_readings WHERE is_synced = FALSE")
        unsynced_readings = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM decisions WHERE is_synced = FALSE")
        unsynced_decisions = cursor.fetchone()[0]
        
        return {
            'last_sync': dict(last_sync) if last_sync else None,
            'unsynced_counts': {
                'zones': unsynced_zones,
                'sensor_readings': unsynced_readings,
                'decisions': unsynced_decisions
            },
            'auto_sync_running': self.sync_running
        }

# Global instance for use across the application
edge_storage = EdgeStorageManager()
