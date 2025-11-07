import React, { useState, useEffect } from 'react';
import {
    Box,
    Card,
    CardContent,
    Typography,
    TextField,
    Checkbox,
    FormControlLabel,
    FormGroup,
    Button,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    Slider,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    Paper,
    Grid,
    Chip,
    Alert,
    CircularProgress
} from '@mui/material';
import { Title, useDataProvider, useNotify } from 'react-admin';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';

interface ForecastResult {
    forecast_data: {
        [team: string]: {
            total_hours: number;
            monthly_breakdown: Array<{
                month: number;
                phase: string;
                hours: number;
            }>;
        };
    };
    total_hours: number;
    baseline_set_used: string;
    characteristics: {
        be_integrations: boolean;
        custom_theme: boolean;
        custom_designs: boolean;
        ux_research: boolean;
    };
    teams_selected: string[];
    estimated_months: number;
}

const TEAMS = ['BE Devs', 'FE Devs', 'Design', 'UX', 'PMs', 'Data'];

const PHASE_COLORS: { [key: string]: string } = {
    'Ramp Up': '#554DFF',
    'Busy (Peak)': '#00FFCE',
    'Ramp Down': '#7D00FF'
};

export const Forecasting = () => {
    const dataProvider = useDataProvider();
    const notify = useNotify();

    // Form state
    const [projectKey, setProjectKey] = useState('');
    const [epicName, setEpicName] = useState('');
    const [epicDescription, setEpicDescription] = useState('');
    const [beIntegrations, setBeIntegrations] = useState(false);
    const [customTheme, setCustomTheme] = useState(false);
    const [customDesigns, setCustomDesigns] = useState(false);
    const [uxResearch, setUxResearch] = useState(false);
    const [teamsSelected, setTeamsSelected] = useState<string[]>([]);
    const [estimatedMonths, setEstimatedMonths] = useState(6);

    // Results state
    const [forecast, setForecast] = useState<ForecastResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [savedForecasts, setSavedForecasts] = useState<any[]>([]);

    useEffect(() => {
        loadSavedForecasts();
    }, []);

    const loadSavedForecasts = async () => {
        try {
            const token = localStorage.getItem('authToken');
            const response = await fetch('http://localhost:4000/api/forecasts', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            const data = await response.json();
            setSavedForecasts(data.forecasts || []);
        } catch (error) {
            console.error('Error loading forecasts:', error);
        }
    };

    const handleTeamToggle = (team: string) => {
        setTeamsSelected(prev =>
            prev.includes(team) ? prev.filter(t => t !== team) : [...prev, team]
        );
    };

    const handleCalculate = async () => {
        if (teamsSelected.length === 0) {
            notify('Please select at least one team', { type: 'error' });
            return;
        }

        setLoading(true);

        try {
            const token = localStorage.getItem('authToken');
            const response = await fetch('http://localhost:4000/api/forecasts/calculate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    be_integrations: beIntegrations,
                    custom_theme: customTheme,
                    custom_designs: customDesigns,
                    ux_research: uxResearch,
                    teams_selected: teamsSelected,
                    estimated_months: estimatedMonths
                })
            });

            const data = await response.json();
            setForecast(data);
            notify('Forecast calculated successfully', { type: 'success' });
        } catch (error) {
            notify('Error calculating forecast', { type: 'error' });
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        if (!forecast || !epicName || !projectKey) {
            notify('Please fill in project and epic name to save', { type: 'error' });
            return;
        }

        try {
            const token = localStorage.getItem('authToken');
            await fetch('http://localhost:4000/api/forecasts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    project_key: projectKey,
                    epic_name: epicName,
                    epic_description: epicDescription,
                    be_integrations: beIntegrations,
                    custom_theme: customTheme,
                    custom_designs: customDesigns,
                    ux_research: uxResearch,
                    teams_selected: teamsSelected,
                    estimated_months: estimatedMonths,
                    forecast_data: forecast.forecast_data,
                    total_hours: forecast.total_hours
                })
            });

            notify('Forecast saved successfully', { type: 'success' });
            loadSavedForecasts();
        } catch (error) {
            notify('Error saving forecast', { type: 'error' });
            console.error(error);
        }
    };

    const prepareChartData = () => {
        if (!forecast) return [];

        const chartData: any[] = [];

        for (let month = 1; month <= estimatedMonths; month++) {
            const monthData: any = { month: `Month ${month}` };

            teamsSelected.forEach(team => {
                const teamForecast = forecast.forecast_data[team];
                if (teamForecast) {
                    const monthlyData = teamForecast.monthly_breakdown.find(m => m.month === month);
                    if (monthlyData) {
                        monthData[team] = monthlyData.hours;
                        monthData[`${team}_phase`] = monthlyData.phase;
                    }
                }
            });

            chartData.push(monthData);
        }

        return chartData;
    };

    return (
        <Box sx={{ p: 3 }}>
            <Title title="Epic Forecasting" />

            <Grid container spacing={3}>
                {/* Input Form */}
                <Grid item xs={12} md={5}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                Epic Configuration
                            </Typography>

                            <TextField
                                label="Project Key"
                                value={projectKey}
                                onChange={(e) => setProjectKey(e.target.value)}
                                fullWidth
                                margin="normal"
                                placeholder="e.g., SRLK"
                            />

                            <TextField
                                label="Epic Name"
                                value={epicName}
                                onChange={(e) => setEpicName(e.target.value)}
                                fullWidth
                                margin="normal"
                                placeholder="e.g., Payment Gateway Integration"
                            />

                            <TextField
                                label="Description (Optional)"
                                value={epicDescription}
                                onChange={(e) => setEpicDescription(e.target.value)}
                                fullWidth
                                margin="normal"
                                multiline
                                rows={2}
                            />

                            <Typography variant="subtitle1" sx={{ mt: 3, mb: 1, fontWeight: 600 }}>
                                Project Characteristics
                            </Typography>

                            <FormGroup>
                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={beIntegrations}
                                            onChange={(e) => setBeIntegrations(e.target.checked)}
                                            color="primary"
                                        />
                                    }
                                    label="Backend Integrations Required (6.63x backend multiplier)"
                                />
                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={customTheme}
                                            onChange={(e) => setCustomTheme(e.target.checked)}
                                            color="primary"
                                        />
                                    }
                                    label="Custom Theme Development (FE)"
                                />
                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={customDesigns}
                                            onChange={(e) => setCustomDesigns(e.target.checked)}
                                            color="primary"
                                        />
                                    }
                                    label="Custom Designs Required"
                                />
                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={uxResearch}
                                            onChange={(e) => setUxResearch(e.target.checked)}
                                            color="primary"
                                        />
                                    }
                                    label="Extensive UX Research/Strategy"
                                />
                            </FormGroup>

                            <Typography variant="subtitle1" sx={{ mt: 3, mb: 1, fontWeight: 600 }}>
                                Teams Involved
                            </Typography>

                            <FormGroup row>
                                {TEAMS.map(team => (
                                    <FormControlLabel
                                        key={team}
                                        control={
                                            <Checkbox
                                                checked={teamsSelected.includes(team)}
                                                onChange={() => handleTeamToggle(team)}
                                                color="secondary"
                                            />
                                        }
                                        label={team}
                                    />
                                ))}
                            </FormGroup>

                            <Typography variant="subtitle1" sx={{ mt: 3, mb: 1, fontWeight: 600 }}>
                                Estimated Duration: {estimatedMonths} months
                            </Typography>

                            <Slider
                                value={estimatedMonths}
                                onChange={(_, value) => setEstimatedMonths(value as number)}
                                min={3}
                                max={18}
                                step={1}
                                marks
                                valueLabelDisplay="auto"
                                color="secondary"
                            />

                            <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
                                <Button
                                    variant="contained"
                                    color="primary"
                                    onClick={handleCalculate}
                                    disabled={loading || teamsSelected.length === 0}
                                    fullWidth
                                >
                                    {loading ? <CircularProgress size={24} /> : 'Calculate Forecast'}
                                </Button>
                            </Box>

                            {forecast && (
                                <Button
                                    variant="outlined"
                                    color="secondary"
                                    onClick={handleSave}
                                    fullWidth
                                    sx={{ mt: 2 }}
                                >
                                    Save Forecast
                                </Button>
                            )}
                        </CardContent>
                    </Card>
                </Grid>

                {/* Results Display */}
                <Grid item xs={12} md={7}>
                    {forecast && (
                        <>
                            <Card sx={{ mb: 3 }}>
                                <CardContent>
                                    <Typography variant="h6" gutterBottom>
                                        Forecast Summary
                                    </Typography>

                                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
                                        <Chip
                                            label={`Total: ${forecast.total_hours.toFixed(2)} hours`}
                                            color="primary"
                                            sx={{ fontWeight: 600, fontSize: '1.1rem' }}
                                        />
                                        <Chip
                                            label={`${estimatedMonths} months`}
                                            color="secondary"
                                        />
                                        <Chip
                                            label={forecast.baseline_set_used.replace('_', ' ').toUpperCase()}
                                            variant="outlined"
                                        />
                                    </Box>

                                    <Alert severity={beIntegrations ? 'warning' : 'info'} sx={{ mb: 2 }}>
                                        {beIntegrations
                                            ? '⚠️ Backend integrations require 6.63x more backend hours. Heavy backend work expected.'
                                            : 'ℹ️ Frontend-focused epic. Design/UX will front-load 85%+ of work in early months.'}
                                    </Alert>
                                </CardContent>
                            </Card>

                            <Card sx={{ mb: 3 }}>
                                <CardContent>
                                    <Typography variant="h6" gutterBottom>
                                        Month-by-Month Breakdown
                                    </Typography>

                                    <ResponsiveContainer width="100%" height={300}>
                                        <BarChart data={prepareChartData()}>
                                            <CartesianGrid strokeDasharray="3 3" />
                                            <XAxis dataKey="month" />
                                            <YAxis label={{ value: 'Hours', angle: -90, position: 'insideLeft' }} />
                                            <Tooltip />
                                            <Legend />
                                            {teamsSelected.map((team, index) => (
                                                <Bar key={team} dataKey={team} stackId="a" fill={`hsl(${index * 60}, 70%, 50%)`} />
                                            ))}
                                        </BarChart>
                                    </ResponsiveContainer>
                                </CardContent>
                            </Card>

                            <Card>
                                <CardContent>
                                    <Typography variant="h6" gutterBottom>
                                        Detailed Forecast by Team
                                    </Typography>

                                    <Table>
                                        <TableHead>
                                            <TableRow>
                                                <TableCell><strong>Team</strong></TableCell>
                                                <TableCell align="right"><strong>Total Hours</strong></TableCell>
                                                <TableCell align="right"><strong>Ramp Up</strong></TableCell>
                                                <TableCell align="right"><strong>Busy Peak</strong></TableCell>
                                                <TableCell align="right"><strong>Ramp Down</strong></TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {teamsSelected.map(team => {
                                                const teamData = forecast.forecast_data[team];
                                                if (!teamData) return null;

                                                const rampUp = teamData.monthly_breakdown.filter(m => m.phase === 'Ramp Up').reduce((sum, m) => sum + m.hours, 0);
                                                const busy = teamData.monthly_breakdown.filter(m => m.phase === 'Busy (Peak)').reduce((sum, m) => sum + m.hours, 0);
                                                const rampDown = teamData.monthly_breakdown.filter(m => m.phase === 'Ramp Down').reduce((sum, m) => sum + m.hours, 0);

                                                return (
                                                    <TableRow key={team}>
                                                        <TableCell><strong>{team}</strong></TableCell>
                                                        <TableCell align="right">{teamData.total_hours.toFixed(2)}h</TableCell>
                                                        <TableCell align="right" sx={{ color: PHASE_COLORS['Ramp Up'] }}>
                                                            {rampUp.toFixed(2)}h
                                                        </TableCell>
                                                        <TableCell align="right" sx={{ color: PHASE_COLORS['Busy (Peak)'] }}>
                                                            {busy.toFixed(2)}h
                                                        </TableCell>
                                                        <TableCell align="right" sx={{ color: PHASE_COLORS['Ramp Down'] }}>
                                                            {rampDown.toFixed(2)}h
                                                        </TableCell>
                                                    </TableRow>
                                                );
                                            })}
                                        </TableBody>
                                    </Table>
                                </CardContent>
                            </Card>
                        </>
                    )}

                    {!forecast && (
                        <Card>
                            <CardContent>
                                <Typography variant="body1" color="textSecondary" align="center">
                                    Configure your epic and click "Calculate Forecast" to see results
                                </Typography>
                            </CardContent>
                        </Card>
                    )}
                </Grid>
            </Grid>

            {/* Saved Forecasts */}
            {savedForecasts.length > 0 && (
                <Card sx={{ mt: 3 }}>
                    <CardContent>
                        <Typography variant="h6" gutterBottom>
                            Saved Forecasts
                        </Typography>

                        <Table>
                            <TableHead>
                                <TableRow>
                                    <TableCell>Project</TableCell>
                                    <TableCell>Epic Name</TableCell>
                                    <TableCell align="right">Total Hours</TableCell>
                                    <TableCell align="right">Months</TableCell>
                                    <TableCell>Teams</TableCell>
                                    <TableCell>Created</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {savedForecasts.map(f => (
                                    <TableRow key={f.id}>
                                        <TableCell>{f.project_key}</TableCell>
                                        <TableCell>{f.epic_name}</TableCell>
                                        <TableCell align="right">{f.total_hours.toFixed(2)}h</TableCell>
                                        <TableCell align="right">{f.estimated_months}</TableCell>
                                        <TableCell>{f.teams_selected.join(', ')}</TableCell>
                                        <TableCell>{new Date(f.created_at).toLocaleDateString()}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            )}
        </Box>
    );
};
