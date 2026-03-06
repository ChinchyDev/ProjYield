-- YieldVision Precision Farming Database Schema
-- PostgreSQL + InfluxDB setup for zone-specific farming

-- PostgreSQL Database Setup
-- Run this in PostgreSQL to create the precision farming database

-- Create database
CREATE DATABASE yieldvision_precision;
\c yieldvision_precision;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Precision zones table (2m x 2m grid zones)
CREATE TABLE precision_zones (
    zone_id VARCHAR(50) PRIMARY KEY,
    field_id VARCHAR(50) NOT NULL,
    center_lat DECIMAL(10,8) NOT NULL,
    center_lon DECIMAL(11,8) NOT NULL,
    area_m2 DECIMAL(8,2) DEFAULT 4.0, -- 2m x 2m
    soil_type VARCHAR(50) DEFAULT 'unknown',
    slope_percent DECIMAL(5,2) DEFAULT 0.0,
    aspect_degrees INTEGER DEFAULT 0,
    drainage_rate VARCHAR(20) DEFAULT 'medium',
    elevation_m DECIMAL(8,2),
    sun_exposure_hours DECIMAL(4,1),
    frost_risk DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Zone-specific sensor readings
CREATE TABLE zone_sensor_data (
    reading_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_id VARCHAR(50) REFERENCES precision_zones(zone_id),
    timestamp TIMESTAMP NOT NULL,
    
    -- Soil measurements at different depths
    soil_moisture_5cm DECIMAL(5,2), -- Surface moisture
    soil_moisture_20cm DECIMAL(5,2), -- Root zone moisture
    soil_moisture_50cm DECIMAL(5,2), -- Deep moisture
    
    -- Nutrient measurements (ppm)
    nitrogen_ppm DECIMAL(8,2),
    phosphorus_ppm DECIMAL(8,2),
    potassium_ppm DECIMAL(8,2),
    
    -- Soil properties
    ph_level DECIMAL(4,2),
    organic_matter_percent DECIMAL(5,2),
    soil_temperature_c DECIMAL(4,1),
    electrical_conductivity DECIMAL(6,2),
    
    -- Environmental data
    air_temperature_c DECIMAL(4,1),
    humidity_percent DECIMAL(5,2),
    solar_radiation_wm2 DECIMAL(6,2),
    
    -- GPS coordinates
    gps_lat DECIMAL(10,8),
    gps_lon DECIMAL(11,8),
    gps_accuracy_m DECIMAL(6,2),
    
    -- Data quality
    sensor_battery_voltage DECIMAL(4,2),
    signal_strength_dbm INTEGER,
    data_quality_score DECIMAL(3,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Zone-specific decisions and recommendations
CREATE TABLE zone_decisions (
    decision_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_id VARCHAR(50) REFERENCES precision_zones(zone_id),
    decision_time TIMESTAMP NOT NULL,
    
    -- Action details
    action_type VARCHAR(50) NOT NULL, -- irrigate, fertilize, plant, etc.
    action_details JSONB NOT NULL, -- Amount, timing, specific parameters
    
    -- Decision evaluation results
    expected_outcome JSONB, -- Monte Carlo simulation results
    confidence_score DECIMAL(3,2),
    risk_assessment JSONB,
    decision_complexity_score DECIMAL(3,2),
    
    -- Economic analysis
    estimated_cost_usd DECIMAL(8,2),
    expected_benefit_usd DECIMAL(8,2),
    roi_multiplier DECIMAL(5,2),
    
    -- Implementation tracking
    implemented_at TIMESTAMP,
    implementation_status VARCHAR(20) DEFAULT 'pending', -- pending, implemented, cancelled
    
    -- Outcome tracking (filled later)
    actual_outcome JSONB,
    actual_cost_usd DECIMAL(8,2),
    actual_benefit_usd DECIMAL(8,2),
    outcome_measured_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crop planting and management
CREATE TABLE zone_crops (
    planting_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_id VARCHAR(50) REFERENCES precision_zones(zone_id),
    
    -- Crop details
    crop_type VARCHAR(50) NOT NULL,
    variety_name VARCHAR(100),
    planting_date DATE NOT NULL,
    expected_harvest_date DATE,
    actual_harvest_date DATE,
    
    -- Planting specifications
    seeds_per_m2 INTEGER,
    planting_depth_cm DECIMAL(4,1),
    row_spacing_cm DECIMAL(4,1),
    
    -- Yield tracking
    expected_yield_kg_per_zone DECIMAL(8,2),
    actual_yield_kg_per_zone DECIMAL(8,2),
    yield_quality_score DECIMAL(3,2),
    
    -- Growth stages tracking
    germination_date DATE,
    flowering_date DATE,
    fruiting_date DATE,
    maturity_date DATE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Irrigation events and schedules
CREATE TABLE zone_irrigation_events (
    irrigation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_id VARCHAR(50) REFERENCES precision_zones(zone_id),
    
    -- Irrigation details
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_minutes INTEGER,
    water_liters_applied DECIMAL(8,2),
    flow_rate_liters_per_minute DECIMAL(6,2),
    
    -- Irrigation parameters
    irrigation_type VARCHAR(50), -- drip, sprinkler, flood
    water_source VARCHAR(50),
    water_ph DECIMAL(4,2),
    water_ec DECIMAL(6,2),
    
    -- Automation details
    trigger_type VARCHAR(50), -- schedule, sensor_threshold, manual
    trigger_value DECIMAL(8,2),
    automated BOOLEAN DEFAULT false,
    
    -- Effectiveness tracking
    pre_irrigation_moisture DECIMAL(5,2),
    post_irrigation_moisture DECIMAL(5,2),
    efficiency_score DECIMAL(3,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fertilizer and amendment applications
CREATE TABLE zone_amendments (
    amendment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_id VARCHAR(50) REFERENCES precision_zones(zone_id),
    
    -- Application details
    application_date TIMESTAMP NOT NULL,
    amendment_type VARCHAR(50) NOT NULL, -- nitrogen, phosphorus, potassium, lime, organic
    product_name VARCHAR(100),
    amount_applied DECIMAL(8,2),
    unit VARCHAR(20), -- kg, liters, etc.
    
    -- Nutrient content
    nitrogen_content_kg DECIMAL(8,2),
    phosphorus_content_kg DECIMAL(8,2),
    potassium_content_kg DECIMAL(8,2),
    
    -- Application method
    application_method VARCHAR(50), -- broadcast, drip, foliar
    incorporation_depth_cm DECIMAL(4,1),
    
    -- Cost tracking
    cost_usd DECIMAL(8,2),
    
    -- Effectiveness tracking
    pre_application_npk JSONB,
    post_application_npk JSONB,
    effectiveness_score DECIMAL(3,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Weather data integration
CREATE TABLE weather_data (
    weather_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMP NOT NULL,
    
    -- Location (for field-level weather)
    field_lat DECIMAL(10,8),
    field_lon DECIMAL(11,8),
    
    -- Current conditions
    temperature_c DECIMAL(4,1),
    humidity_percent DECIMAL(5,2),
    pressure_hpa DECIMAL(6,2),
    wind_speed_ms DECIMAL(4,1),
    wind_direction_degrees INTEGER,
    
    -- Precipitation
    rainfall_mm DECIMAL(6,2),
    snowfall_mm DECIMAL(6,2),
    
    -- Solar
    solar_radiation_wm2 DECIMAL(6,2),
    uv_index DECIMAL(3,1),
    
    -- Forecast data
    forecast_hours_ahead INTEGER,
    is_forecast BOOLEAN DEFAULT false,
    
    -- Data source
    data_source VARCHAR(50), -- openweather, local_station, etc.
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- System alerts and notifications
CREATE TABLE system_alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Alert details
    alert_type VARCHAR(50) NOT NULL, -- irrigation, disease, nutrient, system
    severity_level VARCHAR(20) NOT NULL, -- low, medium, high, critical
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    
    -- Zone/field association
    zone_id VARCHAR(50) REFERENCES precision_zones(zone_id),
    field_id VARCHAR(50),
    
    -- Alert data
    alert_data JSONB, -- Specific sensor readings or conditions
    threshold_value DECIMAL(8,2),
    actual_value DECIMAL(8,2),
    
    -- Notification status
    notification_sent BOOLEAN DEFAULT false,
    notification_method VARCHAR(50), -- sms, email, push
    notification_sent_at TIMESTAMP,
    
    -- Resolution
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance metrics and KPIs
CREATE TABLE performance_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMP NOT NULL,
    
    -- Metric type and value
    metric_type VARCHAR(50) NOT NULL, -- water_efficiency, nutrient_efficiency, etc.
    metric_value DECIMAL(10,4),
    metric_unit VARCHAR(20),
    
    -- Aggregation level
    aggregation_period VARCHAR(20), -- hourly, daily, weekly, monthly
    zone_id VARCHAR(50) REFERENCES precision_zones(zone_id),
    field_id VARCHAR(50),
    
    -- Comparison data
    baseline_value DECIMAL(10,4),
    improvement_percentage DECIMAL(5,2),
    
    -- Data quality
    data_points_count INTEGER,
    confidence_interval JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_zone_sensor_data_zone_timestamp ON zone_sensor_data(zone_id, timestamp DESC);
CREATE INDEX idx_zone_decisions_zone_time ON zone_decisions(zone_id, decision_time DESC);
CREATE INDEX idx_irrigation_events_zone_time ON zone_irrigation_events(zone_id, start_time DESC);
CREATE INDEX idx_amendments_zone_time ON zone_amendments(zone_id, application_date DESC);
CREATE INDEX idx_weather_data_timestamp ON weather_data(timestamp DESC);
CREATE INDEX idx_alerts_created_at ON system_alerts(created_at DESC);

-- Create trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_precision_zones_updated_at BEFORE UPDATE
    ON precision_zones FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_zone_crops_updated_at BEFORE UPDATE
    ON zone_crops FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- InfluxDB Setup Instructions
-- Run these commands in InfluxDB CLI or web interface

/*
# Create InfluxDB database
CREATE database yieldvision_timeseries

# Create retention policies
create retention policy "one_year" on "yieldvision_timeseries" duration 365d replication 1 default
create retention policy "six_months" on "yieldvision_timeseries" duration 180d replication 1
create retention policy "one_month" on "yieldvision_timeseries" duration 30d replication 1

# Create continuous queries for downsampling
# Downsample raw sensor data to hourly averages
create continuous query "cq_hourly_averages" on "yieldvision_timeseries"
begin
  select mean(*) into "one_year"."sensor_readings_hourly" from "sensor_readings" group by time(1h), zone_id
end

# Downsample to daily averages
create continuous query "cq_daily_averages" on "yieldvision_timeseries"
begin
  select mean(*) into "six_months"."sensor_readings_daily" from "sensor_readings" group by time(1d), zone_id
end

# Downsample to weekly averages
create continuous query "cq_weekly_averages" on "yieldvision_timeseries"
begin
  select mean(*) into "one_month"."sensor_readings_weekly" from "sensor_readings" group by time(1w), zone_id
end
*/

-- Sample Data Insertion (for testing)
INSERT INTO precision_zones (zone_id, field_id, center_lat, center_lon, soil_type, slope_percent) VALUES
('Z_1.286400_36.817200', 'field_001', 1.2864, 36.8172, 'loamy', 2.5),
('Z_1.286402_36.817202', 'field_001', 1.286402, 36.817202, 'sandy', 5.0),
('Z_1.286404_36.817204', 'field_001', 1.286404, 36.817204, 'clay', 1.0);

-- Create views for common queries
CREATE VIEW zone_summary AS
SELECT 
    pz.zone_id,
    pz.center_lat,
    pz.center_lon,
    pz.soil_type,
    pz.slope_percent,
    COUNT(zsd.reading_id) as reading_count,
    MAX(zsd.timestamp) as last_reading,
    AVG(zsd.soil_moisture_20cm) as avg_moisture,
    AVG(zsd.nitrogen_ppm) as avg_nitrogen,
    AVG(zsd.ph_level) as avg_ph
FROM precision_zones pz
LEFT JOIN zone_sensor_data zsd ON pz.zone_id = zsd.zone_id
WHERE pz.is_active = true
GROUP BY pz.zone_id, pz.center_lat, pz.center_lon, pz.soil_type, pz.slope_percent;

-- Create decision summary view
CREATE VIEW decision_summary AS
SELECT 
    zd.zone_id,
    COUNT(zd.decision_id) as total_decisions,
    COUNT(CASE WHEN zd.implementation_status = 'implemented' THEN 1 END) as implemented_decisions,
    AVG(zd.confidence_score) as avg_confidence,
    AVG(zd.roi_multiplier) as avg_roi,
    SUM(zd.estimated_cost_usd) as total_estimated_cost,
    SUM(CASE WHEN zd.actual_benefit_usd IS NOT NULL THEN zd.actual_benefit_usd ELSE 0 END) as total_actual_benefit
FROM zone_decisions zd
GROUP BY zd.zone_id;

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO yieldvision_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO yieldvision_user;
